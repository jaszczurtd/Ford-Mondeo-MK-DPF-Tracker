#pragma once

#include <JaszczurHAL.h>
#include <hal/hal_app.h>
#include <tools.h>
#include <Credentials.h>


// =============================================================
// KONFIGURACJA
// =============================================================

#define WATCHDOG_TIME 7000
#define VERSION  "v0.4"

#define DEBUG_SERIAL_FLUSH_ENABLED false
#define MODEM_BAUD_RATE 115200UL

#define MQTT_CLIENT_ID    "dpf-tracker"
#define MQTT_TOPIC_DATA   "dpf/data"
#define MQTT_TOPIC_STATUS "dpf/status"
#define MQTT_TOPIC_CMD    "dpf/cmd"
#define MQTT_CMD_MODEM_RESET "modem_reset"
#define MQTT_KEEPALIVE    120
#define MQTT_CLIENT_INDEX 0
#define MODEM_PWR_PULSE_MS 1500

#define APN               "internet"
#define SSL_CA_CERT       "ca.pem"

#define PIN_MODEM_TX      4
#define PIN_MODEM_RX      5
#define PIN_I2C_SDA       0
#define PIN_I2C_SCL       1
#define PIN_ADC_DP        26
#define PIN_PUMP_PULSE    2
#define PIN_GLOW_PLUG     3
#define PIN_MODEM_PWR     6
#define PIN_RGB           16

#define MCP9600_ADDR_PRE_DPF   0x60
#define MCP9600_ADDR_MID_DPF   0x67

#define SENSOR_INTERVAL_MS     500
#define MQTT_PUBLISH_INTERVAL  2000
#define NETWORK_TIME_INTERVAL_MS 60000
#define GNSS_LOCATION_INTERVAL_MS 5000
#define GNSS_ENABLE_TIMEOUT_MS 3000
#define GNSS_QUERY_TIMEOUT_MS 3000
#define CELL_LOCATION_INTERVAL_MS 15000
#define RECONNECT_INTERVAL_MS  30000
#define MAX_RECONNECT_BEFORE_RESET 3
#define MODEM_WARMUP_MS        15000

#define ADC_DIVIDER_RATIO      1.515f
#define ADC_VREF               3.3f
#define ADC_MAX_VALUE          4095.0f

#define AT_BUF_SIZE 1024

enum CriticalError {
  ERR_NONE = 0,
  ERR_MODEM_NO_AT,
  ERR_SIM_NOT_READY,
  ERR_NETWORK_NOT_REGISTERED,
  ERR_PDP_ACTIVATE,
  ERR_MQTT_CONNECT,
  ERR_MQTT_PUBLISH,
  ERR_MQTT_SUBSCRIBE
};

enum LedStatus { LED_CONNECTING, LED_OK, LED_ERROR, LED_SENDING };

struct SensorData {
  float egt_pre       = 0.0f;
  float egt_mid       = 0.0f;
  float dp_voltage    = 0.0f;
  uint16_t dp_raw     = 0;

  volatile uint32_t pump_pulse_count = 0;
  volatile uint32_t pump_last_us     = 0;
  volatile uint32_t pump_period_us   = 0;
  float pump_freq_hz  = 0.0f;

  volatile bool glow_state        = false;
  volatile uint32_t glow_on_us    = 0;
  volatile uint32_t glow_off_us   = 0;
  volatile uint32_t glow_on_duration_ms    = 0;
};

bool mqttPublish(const char* topic, const char* payload);
void handleCriticalFailure(CriticalError err);
