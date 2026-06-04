/*
 * DPF Regeneration Tracker — Firmware RP2040 (RP2040-Zero)
 * =========================================================
 * v0.4 — RP2040-Zero, RGB NeoPixel LED, watchdog fixes
 *
 * Monitors the DPF regeneration system (Mondeo Mk4 2.0 TDCi PSA):
 *   - 2x EGT probe (K-type thermocouple) via MCP9600 (I2C)
 *   - DPF differential pressure sensor (ADC)
 *   - Fuel dosing pump pulses (GPIO interrupt)
 *   - Vaporizer glow plug state (GPIO interrupt)
 *
 * Sends data over LTE Cat-1 (A7670E) → MQTT/TLS → Mosquitto (RPi5)
 *
 * Pinout:
 *   GPIO0  - I2C0 SDA (MCP9600 x2)
 *   GPIO1  - I2C0 SCL (MCP9600 x2)
 *   GPIO2  - interrupt: dosing pump pulses
 *   GPIO3  - interrupt: glow plug state
 *   GPIO4  - Serial2 TX → modem RX
 *   GPIO5  - Serial2 RX ← modem TX
 *   GPIO6  - modem power relay
 *   GPIO16 - NeoPixel RGB LED (RP2040-Zero)
 *   GPIO26 - ADC0: differential pressure sensor
 */

#include "tracker.h"

// =============================================================
// GLOBAL VARIABLES
// =============================================================

static CriticalError last_critical_error = ERR_NONE;
hal_thermocouple_t egt_pre_dpf = NULL;
hal_thermocouple_t egt_mid_dpf = NULL;

static SensorData sensors;

static bool modem_ready = false;
static bool mqtt_connected = false;
static uint32_t last_sensor_ms = 0;
static uint32_t last_publish_ms = 0;
static uint32_t last_cell_location_ms = 0;
static uint32_t last_reconnect_ms = 0;
static uint8_t reconnect_fails = 0;

static char modem_rx_buf[AT_BUF_SIZE];
static char network_time[32] = "";
static hal_uart_t modem_serial = nullptr;
static hal_simcom_a76xx_t modem = nullptr;
static hal_simcom_a76xx_cell_location_t cell_location = {};
static bool cell_location_valid = false;
static uint32_t cell_location_last_ok_ms = 0;
static int cell_location_last_error = HAL_SIMCOM_A76XX_NOT_READY;

// Set from the MQTT message callback; consumed in loop_1() so the hard
// reset runs outside the URC dispatch path.
static volatile bool pending_modem_reset = false;

static LedStatus led_status = LED_CONNECTING;
static LedStatus led_prev_status = LED_CONNECTING;
static uint32_t led_last_ms = 0;
static bool led_on = false;

static cJSON* addFixed2Number(cJSON* root, const char* key, float value) {
  char num_buf[24] = {0};
  (void)snprintf(num_buf, sizeof(num_buf), "%.2f", (double)roundToN(value, 2));
  return cJSON_AddRawToObject(root, key, num_buf);
}

// =============================================================
// RGB LED STATUS
// =============================================================

void ledInit() {
  hal_rgb_led_init_ex(PIN_RGB, 1, HAL_RGB_LED_PIXEL_GRB_KHZ800);
}

void ledSetStatus(LedStatus s) {
  if (s == LED_SENDING) {
    led_prev_status = led_status;
  }

  led_status = s;
  led_last_ms = 0;
  led_on = false;
}

void ledUpdate() {
  uint32_t now = hal_millis();

  switch (led_status) {
    case LED_CONNECTING:
      if (now - led_last_ms >= 250) {
        led_last_ms = now;
        led_on = !led_on;
        hal_rgb_led_set_color(led_on ? HAL_RGB_LED_GREEN : HAL_RGB_LED_NONE);
      }
      break;

    case LED_OK:
      hal_rgb_led_set_color(HAL_RGB_LED_GREEN);
      break;

    case LED_ERROR:
      if (now - led_last_ms >= 300) {
        led_last_ms = now;
        led_on = !led_on;
        hal_rgb_led_set_color(led_on ? HAL_RGB_LED_RED : HAL_RGB_LED_NONE);
      }
      break;

    case LED_SENDING:
      hal_rgb_led_set_color(HAL_RGB_LED_PURPLE);
      break;
  }
}

void ledSendingDone() {
  if (led_status == LED_SENDING) {
    led_status = led_prev_status;
    led_last_ms = 0;
    led_on = false;
  }
}

void smartDelay(uint32_t ms) {
  uint32_t start = hal_millis();
  while (hal_millis() - start < ms) {
    hal_watchdog_feed();
    ledUpdate();
    hal_delay_ms(1);
  }
}

// =============================================================
// INTERRUPTS
// =============================================================

void isr_pump_pulse() {
  uint32_t now = hal_micros();
  if (sensors.pump_last_us > 0) {
    sensors.pump_period_us = now - sensors.pump_last_us;
  }

  sensors.pump_last_us = now;
  sensors.pump_pulse_count++;
}

void isr_glow_plug() {
  uint32_t now = hal_micros();

  // NPN common-emitter: inverted logic
  // LOW = glow plug ON, HIGH = glow plug OFF
  bool pin_low = !hal_gpio_read(PIN_GLOW_PLUG);
  if (pin_low) {
    sensors.glow_state = true;
    sensors.glow_on_us = now;
  } else {
    sensors.glow_state = false;
    sensors.glow_off_us = now;
    if (sensors.glow_on_us > 0) {
      sensors.glow_on_duration_ms = (now - sensors.glow_on_us) / 1000;
    }
  }
}

// =============================================================
// MODEM POWER CONTROL
// =============================================================
//
// The A7670E module on this board has NO PWRKEY broken out — it boots
// the moment VCC is applied. Power is gated by an external relay
// driven from PIN_MODEM_PWR:
//   HIGH = relay closed = modem powered (idle state)
//   LOW  = relay open   = modem unpowered
//
// That polarity matches hal_simcom_a76xx_power_toggle()'s waveform
// (idle HIGH → active-LOW pulse → HIGH), so we wire PIN_MODEM_PWR as
// the driver's pwr_pin and reuse the HAL helper for power-cycling.
// We don't call hal_simcom_a76xx_hard_reset() because it issues two
// pulses with a 5 s gap (PWRKEY "force off then back on" semantics);
// for a relay-gated module a single power-cycle is sufficient.

static void modemPwrInit() {
  hal_gpio_set_mode(PIN_MODEM_PWR, HAL_GPIO_OUTPUT);
  hal_gpio_write(PIN_MODEM_PWR, true);  // power on (relay closed)
}

// Power-cycle the modem through the relay and wait for it to boot.
// Watchdog is fed throughout via the tick callback installed on the
// AT engine (hal_modem_at_sleep_ms() invokes it every ~20 ms).
static void modemHardResetRelay() {
  if (modem == nullptr) {
    return;
  }
  deb("[MODEM] hard reset via power relay");
  (void)hal_simcom_a76xx_power_toggle(modem, MODEM_PWR_PULSE_MS);
  hal_modem_at_sleep_ms(hal_simcom_a76xx_get_at(modem), MODEM_WARMUP_MS);
  deb("[MODEM] hard reset complete");
}

// =============================================================
// ERROR HANDLING
// =============================================================

void handleCriticalFailure(CriticalError err) {
  switch (err) {
    case ERR_MQTT_CONNECT:
    case ERR_MQTT_PUBLISH:
    case ERR_MQTT_SUBSCRIBE:
      mqtt_connected = false;
      break;

    case ERR_MODEM_NO_AT:
    case ERR_SIM_NOT_READY:
    case ERR_NETWORK_NOT_REGISTERED:
    case ERR_PDP_ACTIVATE:
      mqtt_connected = false;
      modem_ready = false;
      break;

    default:
      break;
  }
}

static void setCriticalError(CriticalError err, const char* msg) {
  last_critical_error = err;
  hal_serial_print("[CRIT] ");
  derr("%s", (msg != nullptr) ? msg : "(null)");
  handleCriticalFailure(last_critical_error);
}

// Engine-side tick: invoked from inside long blocking waits in
// hal_modem_at / hal_simcom_a76xx. Without this hook the modem
// bring-up (up to ~75 s across wait_boot + sim ready + network
// registration) would starve the application watchdog.
//
// The driver guarantees this is called at least every ~20 ms.  Runs
// under the engine mutex — must not touch the modem.
static void modemTick(void* user) {
  (void)user;
  hal_watchdog_feed();
  ledUpdate();
}

// =============================================================
// MQTT INCOMING MESSAGE CALLBACK
// =============================================================

// Triggered from hal_simcom_a76xx_mqtt_poll() once a full CMQTTRX*
// sequence has been reassembled.  The buffers are owned by the driver
// and only live for the duration of this call.
//
// Currently supported commands (topic "dpf/cmd"):
//   - "modem_reset"  -> request a hard reset of the modem
static void onMqttMessage(int client_index,
                          const char* topic,
                          const uint8_t* payload,
                          size_t payload_len,
                          void* user) {
  (void)client_index;
  (void)user;

  if ((topic == nullptr) || (payload == nullptr)) {
    return;
  }

  deb("[MQTT] RX topic=%s len=%u", topic, (unsigned)payload_len);

  if (strcmp(topic, MQTT_TOPIC_CMD) != 0) {
    return;
  }

  const size_t cmd_len = strlen(MQTT_CMD_MODEM_RESET);
  if ((payload_len == cmd_len) &&
      (memcmp(payload, MQTT_CMD_MODEM_RESET, cmd_len) == 0)) {
    deb("[CMD] modem_reset requested via MQTT");
    pending_modem_reset = true;
  } else {
    deb("[CMD] unknown command (%u bytes), ignored", (unsigned)payload_len);
  }
}

// =============================================================
// NETWORK TIME
// =============================================================

static bool updateNetworkTime() {
  if (modem == nullptr) {
    return false;
  }

  if (hal_simcom_a76xx_get_network_time_iso8601(modem,
                                                network_time,
                                                sizeof(network_time))
      != HAL_SIMCOM_A76XX_OK) {
    return false;
  }

  deb("[TIME] %s", network_time);
  return true;
}

static hal_simcom_a76xx_result_t updateCellLocation() {
  if (modem == nullptr) {
    return HAL_SIMCOM_A76XX_INVALID_ARG;
  }

  hal_simcom_a76xx_cell_location_t loc = {};
  hal_simcom_a76xx_result_t r =
      hal_simcom_a76xx_get_cell_location(modem, &loc, 12000u);
  if (r != HAL_SIMCOM_A76XX_OK) {
    const char* resp = hal_modem_at_last_response(hal_simcom_a76xx_get_at(modem));
    deb("[CELL] CLBS error=%d resp=%s", (int)r, (resp != nullptr) ? resp : "(null)");
    return r;
  }

  cell_location = loc;
  cell_location_valid = true;
  cell_location_last_ok_ms = hal_millis();
  cell_location_last_error = HAL_SIMCOM_A76XX_OK;
  deb("[CELL] lat=%.6f lon=%.6f acc=%d m",
      cell_location.latitude_deg,
      cell_location.longitude_deg,
      cell_location.accuracy_m);
  return HAL_SIMCOM_A76XX_OK;
}

// =============================================================
// MODEM INITIALIZATION
// =============================================================

bool modemInit() {
  if (modem_serial == nullptr) {
    modem_serial = hal_uart_create(HAL_UART_PORT_2, PIN_MODEM_RX, PIN_MODEM_TX);
  }

  if (modem_serial == nullptr) {
    setCriticalError(ERR_MODEM_NO_AT, "Modem UART init failed");
    return false;
  }

  hal_uart_set_tx(modem_serial, PIN_MODEM_TX);
  hal_uart_set_rx(modem_serial, PIN_MODEM_RX);
  hal_uart_begin(modem_serial, MODEM_BAUD_RATE, SERIAL_8N1);
  deb("[UART] Modem serial via JaszczurHAL on GPIO%u/%u @ %lu",
      (unsigned)PIN_MODEM_TX, (unsigned)PIN_MODEM_RX,
      (unsigned long)MODEM_BAUD_RATE);

  if (modem == nullptr) {
    hal_simcom_a76xx_config_t cfg = {};
    cfg.uart = modem_serial;
    // Wire the power-control relay into the HAL driver: its waveform
    // (idle HIGH → active-LOW pulse → HIGH) matches our relay polarity,
    // so modemHardResetRelay() can simply call power_toggle().
    cfg.pwr_pin = PIN_MODEM_PWR;
    cfg.rx_buf = modem_rx_buf;
    cfg.rx_buf_size = sizeof(modem_rx_buf);
    cfg.default_at_timeout_ms = 3000;
    modem = hal_simcom_a76xx_create(&cfg);
    if (modem == nullptr) {
      setCriticalError(ERR_MODEM_NO_AT, "SimCom driver create failed");
      return false;
    }

    static const char* secrets[] = { MQTT_USER, MQTT_PASSWORD };
    hal_modem_at_set_log_filter(hal_simcom_a76xx_get_at(modem),
                                secrets,
                                sizeof(secrets) / sizeof(secrets[0]));
    hal_modem_at_set_tick_callback(hal_simcom_a76xx_get_at(modem),
                                   modemTick, nullptr);
    hal_simcom_a76xx_mqtt_set_message_callback(modem, onMqttMessage, nullptr);
  }

  ledSetStatus(LED_CONNECTING);
  last_critical_error = ERR_NONE;

  hal_simcom_a76xx_wait_boot(modem, MODEM_WARMUP_MS);

  if (hal_simcom_a76xx_init(modem) != HAL_SIMCOM_A76XX_OK) {
    setCriticalError(ERR_MODEM_NO_AT, "No response to AT");
    return false;
  }

  if (hal_simcom_a76xx_wait_sim_ready(modem, 5000) != HAL_SIMCOM_A76XX_OK) {
    setCriticalError(ERR_SIM_NOT_READY, "SIM not ready");
    return false;
  }

  if (hal_simcom_a76xx_wait_network_registered(modem, 60000)
      != HAL_SIMCOM_A76XX_OK) {
    setCriticalError(ERR_NETWORK_NOT_REGISTERED, "Network registration failed");
    return false;
  }

  hal_simcom_a76xx_apn_t apn_cfg = {};
  apn_cfg.apn = APN;
  if (hal_simcom_a76xx_attach_pdp(modem, &apn_cfg) != HAL_SIMCOM_A76XX_OK) {
    setCriticalError(ERR_PDP_ACTIVATE, "PDP activation failed");
    return false;
  }

  return true;
}

// =============================================================
// MQTT
// =============================================================

bool mqttConnect() {
  if (modem == nullptr) {
    setCriticalError(ERR_MQTT_CONNECT, "modem not initialised");
    return false;
  }

  ledSetStatus(LED_CONNECTING);
  last_critical_error = ERR_NONE;

  hal_simcom_a76xx_mqtt_config_t mq = {};
  mq.broker_host  = MQTT_BROKER_IP;
  mq.broker_port  = MQTT_BROKER_SECURE_PORT;
  mq.client_id    = MQTT_CLIENT_ID;
  mq.username     = MQTT_USER;
  mq.password     = MQTT_PASSWORD;
  mq.keepalive_s  = MQTT_KEEPALIVE;
  mq.clean_session = true;
  mq.client_index = MQTT_CLIENT_INDEX;
  mq.ssl.enabled            = true;
  mq.ssl.ssl_context_id     = 0;
  mq.ssl.ca_cert_name       = SSL_CA_CERT;
  mq.ssl.ignore_local_time  = true;
  mq.ssl.enable_sni         = false;
  mq.ssl.sslversion         = 4;   // TLS 1.2
  mq.ssl.authmode           = 1;   // verify server cert only

  if (hal_simcom_a76xx_mqtt_connect(modem, &mq) != HAL_SIMCOM_A76XX_OK) {
    setCriticalError(ERR_MQTT_CONNECT, "MQTT connect failed");
    ledSetStatus(LED_ERROR);
    return false;
  }

  if (hal_simcom_a76xx_mqtt_subscribe(modem, MQTT_CLIENT_INDEX,
                                      MQTT_TOPIC_CMD, 1)
      != HAL_SIMCOM_A76XX_OK) {
    setCriticalError(ERR_MQTT_SUBSCRIBE, "MQTT subscribe (cmd) failed");
    ledSetStatus(LED_ERROR);
    return false;
  }
  deb("[MQTT] subscribed to %s", MQTT_TOPIC_CMD);

  if (!mqttPublish(MQTT_TOPIC_STATUS, "{\"status\":\"online\"}")) {
    setCriticalError(ERR_MQTT_PUBLISH, "Initial status publish failed");
    ledSetStatus(LED_ERROR);
    return false;
  }

  ledSetStatus(LED_OK);
  return true;
}

bool mqttPublish(const char* topic, const char* payload) {
  if ((modem == nullptr) || (topic == nullptr) || (payload == nullptr)) {
    return false;
  }

  ledSetStatus(LED_SENDING);
  last_critical_error = ERR_NONE;

  hal_simcom_a76xx_result_t r =
      hal_simcom_a76xx_mqtt_publish(modem, MQTT_CLIENT_INDEX, topic,
                                    payload, strlen(payload), 1);
  if (r != HAL_SIMCOM_A76XX_OK) {
    setCriticalError(ERR_MQTT_PUBLISH, "MQTT publish failed");
    ledSetStatus(LED_ERROR);
    return false;
  }

  ledSendingDone();
  return true;
}

// Passive boot-URC waiter.
// =============================================================
// SENSORS
// =============================================================

void sensorsInit() {
  hal_adc_set_resolution(12);

  hal_thermocouple_config_t egt_cfg;
  egt_cfg.chip             = HAL_THERMOCOUPLE_CHIP_MCP9600;
  egt_cfg.bus.i2c.sda_pin  = PIN_I2C_SDA;
  egt_cfg.bus.i2c.scl_pin  = PIN_I2C_SCL;
  egt_cfg.bus.i2c.clock_hz = HAL_I2C_CLOCK_STANDARD_HZ;
  egt_cfg.bus.i2c.i2c_addr = MCP9600_ADDR_PRE_DPF;
  egt_pre_dpf = hal_thermocouple_init(&egt_cfg);
  if (!egt_pre_dpf) {
    derr("[EGT] MCP9600 #1 not found!");
  } else {
    hal_thermocouple_set_type(egt_pre_dpf, HAL_THERMOCOUPLE_TYPE_K);
    hal_thermocouple_set_adc_resolution(egt_pre_dpf, HAL_THERMOCOUPLE_ADC_RES_18);
    hal_thermocouple_set_ambient_resolution(egt_pre_dpf, HAL_THERMOCOUPLE_AMBIENT_RES_0_0625);
    hal_thermocouple_set_filter(egt_pre_dpf, 3);
    hal_thermocouple_enable(egt_pre_dpf, true);
    deb("[EGT] MCP9600 #1 OK");
  }

  egt_cfg.bus.i2c.i2c_addr = MCP9600_ADDR_MID_DPF;
  egt_mid_dpf = hal_thermocouple_init(&egt_cfg);
  if (!egt_mid_dpf) {
    derr("[EGT] MCP9600 #2 not found!");
  } else {
    hal_thermocouple_set_type(egt_mid_dpf, HAL_THERMOCOUPLE_TYPE_K);
    hal_thermocouple_set_adc_resolution(egt_mid_dpf, HAL_THERMOCOUPLE_ADC_RES_18);
    hal_thermocouple_set_ambient_resolution(egt_mid_dpf, HAL_THERMOCOUPLE_AMBIENT_RES_0_0625);
    hal_thermocouple_set_filter(egt_mid_dpf, 3);
    hal_thermocouple_enable(egt_mid_dpf, true);
    deb("[EGT] MCP9600 #2 OK");
  }

  hal_gpio_set_mode(PIN_ADC_DP, HAL_GPIO_INPUT);

  hal_gpio_set_mode(PIN_PUMP_PULSE, HAL_GPIO_INPUT_PULLUP);
  hal_gpio_attach_interrupt(PIN_PUMP_PULSE, isr_pump_pulse, HAL_GPIO_IRQ_FALLING);

  hal_gpio_set_mode(PIN_GLOW_PLUG, HAL_GPIO_INPUT_PULLUP);
  hal_gpio_attach_interrupt(PIN_GLOW_PLUG, isr_glow_plug, HAL_GPIO_IRQ_CHANGE);

}

void sensorsRead() {
  float vadc = 0.0f;
  uint32_t period = 0;
  uint32_t last_pulse = 0;

  sensors.egt_pre = hal_thermocouple_read(egt_pre_dpf);
  sensors.egt_mid = hal_thermocouple_read(egt_mid_dpf);

  sensors.dp_raw = (uint16_t)hal_adc_read(PIN_ADC_DP);
  vadc = (sensors.dp_raw / ADC_MAX_VALUE) * ADC_VREF;
  sensors.dp_voltage = vadc * ADC_DIVIDER_RATIO;

  hal_critical_section_enter();
  period = sensors.pump_period_us;
  last_pulse = sensors.pump_last_us;
  hal_critical_section_exit();

  if (period > 0 && (hal_micros() - last_pulse) < 2000000) {
    sensors.pump_freq_hz = 1000000.0f / (float)period;
  } else {
    sensors.pump_freq_hz = 0.0f;
  }
}

// =============================================================
// JSON PAYLOAD
// =============================================================

char* buildPayload() {
  uint32_t pump_count = 0;
  float pump_freq = 0.0f;
  bool glow = false;
  uint32_t glow_dur = 0;
  char* json = nullptr;
  cJSON* root = nullptr;

  hal_critical_section_enter();
  pump_count = sensors.pump_pulse_count;
  sensors.pump_pulse_count = 0;
  pump_freq = sensors.pump_freq_hz;
  glow = sensors.glow_state;
  glow_dur = sensors.glow_on_duration_ms;
  hal_critical_section_exit();

  NONULL(root = cJSON_CreateObject());

  NONULL(cJSON_AddStringToObject(root, "version", VERSION));
  NONULL(cJSON_AddStringToObject(root, "time", network_time[0] ? network_time : ""));
  NONULL(addFixed2Number(root, "egt_pre", sensors.egt_pre));
  NONULL(addFixed2Number(root, "egt_mid", sensors.egt_mid));
  NONULL(cJSON_AddNumberToObject(root, "dp_voltage", sensors.dp_voltage));
  NONULL(cJSON_AddNumberToObject(root, "dp_raw", sensors.dp_raw));
  NONULL(cJSON_AddNumberToObject(root, "pump_onoff_period", pump_freq));
  NONULL(cJSON_AddNumberToObject(root, "pump_cnt", pump_count));
  NONULL(cJSON_AddNumberToObject(root, "glow", glow ? 1 : 0));
  NONULL(cJSON_AddNumberToObject(root, "glow_dur", glow_dur));
  NONULL(addFixed2Number(root, "mcu_temp", hal_read_chip_temp()));
  NONULL(cJSON_AddNumberToObject(root, "cell_valid", cell_location_valid ? 1 : 0));
  NONULL(cJSON_AddNumberToObject(root, "cell_error", cell_location_last_error));
  if (cell_location_valid) {
    NONULL(cJSON_AddNumberToObject(root, "cell_age_ms", hal_millis() - cell_location_last_ok_ms));
    if (cell_location.speed_kmh >= 0.0f) {
      NONULL(addFixed2Number(root, "cell_speed_kmh", cell_location.speed_kmh));
    } else {
      NONULL(cJSON_AddNumberToObject(root, "cell_speed_kmh", -1));
    }
  } else {
    NONULL(cJSON_AddNumberToObject(root, "cell_age_ms", -1));
    NONULL(cJSON_AddNumberToObject(root, "cell_speed_kmh", -1));
  }
  if (cell_location_valid) {
    NONULL(cJSON_AddNumberToObject(root, "cell_lat", cell_location.latitude_deg));
    NONULL(cJSON_AddNumberToObject(root, "cell_lng", cell_location.longitude_deg));
    NONULL(cJSON_AddNumberToObject(root, "cell_acc_m", cell_location.accuracy_m));
  }
  NONULL(cJSON_AddNumberToObject(root, "ms", hal_millis()));

  NONULL(json = cJSON_PrintUnformatted(root));

error:
  cJSON_Delete(root);
  return json;
}

// =============================================================
// SETUP
// =============================================================

void setup_1() {
  hal_watchdog_enable(WATCHDOG_TIME, false);
  hal_serial_begin(9600);
  ledInit();
  ledSetStatus(LED_CONNECTING);
  smartDelay(3000);

  deb("DPF Tracker ");
  deb(VERSION);

  modemPwrInit();
  sensorsInit();

  smartDelay(1500);

  modem_ready = modemInit();
  if (modem_ready) {
    mqtt_connected = mqttConnect();
  }

  if (!mqtt_connected) {
    ledSetStatus(LED_ERROR);
  }
}

// =============================================================
// LOOP
// =============================================================

void loop_1() {
  uint32_t now = hal_millis();
  char* payload = nullptr;

  hal_watchdog_feed();
  ledUpdate();

  if (mqtt_connected && (modem != nullptr)) {
    hal_simcom_a76xx_mqtt_poll(modem);
  }

  if (pending_modem_reset) {
    pending_modem_reset = false;
    deb("[CMD] executing modem hard reset");
    modemHardResetRelay();
    cell_location_valid = false;
    cell_location.speed_kmh = -1.0f;
    cell_location_last_ok_ms = 0;
    cell_location_last_error = HAL_SIMCOM_A76XX_NOT_READY;
    mqtt_connected = false;
    modem_ready = false;
    reconnect_fails = 0;
    last_reconnect_ms = now;
    ledSetStatus(LED_CONNECTING);
    return;
  }

  if (now - last_sensor_ms >= SENSOR_INTERVAL_MS) {
    last_sensor_ms = now;
    sensorsRead();
  }

  if (modem_ready && (now - last_cell_location_ms >= CELL_LOCATION_INTERVAL_MS)) {
    last_cell_location_ms = now;
    hal_simcom_a76xx_result_t lr = updateCellLocation();
    if (lr != HAL_SIMCOM_A76XX_OK) {
      cell_location_last_error = lr;
      if (!cell_location_valid) {
        deb("[CELL] location unavailable (err=%d)", (int)lr);
      } else {
        deb("[CELL] update failed (err=%d), keeping last fix", (int)lr);
      }
    }
  }

  if (mqtt_connected && (now - last_publish_ms >= MQTT_PUBLISH_INTERVAL)) {
    last_publish_ms = now;
    updateNetworkTime();

    payload = buildPayload();
    if (payload != nullptr) {
      deb("[PUB] %s", payload);

      if (!mqttPublish(MQTT_TOPIC_DATA, payload)) {
        // Error state is already handled inside mqttPublish().
      }
      hal_watchdog_feed();

      free(payload);
    } else {
      derr("memory allocation problem!");
      ledSetStatus(LED_ERROR);
      return;
    }
  }

  if (!mqtt_connected && (now - last_reconnect_ms >= RECONNECT_INTERVAL_MS)) {
    last_reconnect_ms = now;
    reconnect_fails++;
    ledSetStatus(LED_CONNECTING);

    if (reconnect_fails >= MAX_RECONNECT_BEFORE_RESET) {
      modemHardResetRelay();
      cell_location_valid = false;
      cell_location.speed_kmh = -1.0f;
      cell_location_last_ok_ms = 0;
      cell_location_last_error = HAL_SIMCOM_A76XX_NOT_READY;
      modem_ready = false;
      reconnect_fails = 0;
    }

    if (!modem_ready) {
      modem_ready = modemInit();
    }

    if (modem_ready) {
      mqtt_connected = mqttConnect();
      if (mqtt_connected) {
        reconnect_fails = 0;
      }
    }

    if (!mqtt_connected) {
      ledSetStatus(LED_ERROR);
    }
  }
}
