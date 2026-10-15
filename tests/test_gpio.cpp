// Test the production initialization and ISRs; replace only hardware I/O.
#include "../tracker.cpp"
#include <array>
#include <cassert>

static std::array<bool, 256> levels;
static std::array<hal_gpio_mode_t, 256> modes;
static std::array<void (*)(void), 256> callbacks;
static uint32_t now_us = 1000;

extern "C" {
uint32_t hal_micros(void) { return now_us; }
uint32_t hal_millis(void) { return now_us / 1000; }
void hal_deb(const char *, ...) {}
void hal_derr(const char *, ...) {}
void hal_adc_set_resolution(uint8_t) {}
hal_thermocouple_t hal_thermocouple_init(const hal_thermocouple_config_t *) { return nullptr; }
void hal_gpio_set_mode(uint8_t pin, hal_gpio_mode_t mode) { modes.at(pin) = mode; }
bool hal_gpio_read(uint8_t pin) { return levels.at(pin); }
void hal_gpio_attach_interrupt(uint8_t pin, void (*callback)(void), hal_gpio_irq_mode_t mode) {
  assert(mode == HAL_GPIO_IRQ_CHANGE);
  callbacks.at(pin) = callback;
}
}

int main() {
  const uint8_t pump = JH_HW_NODE_PUMP_PULSE_PIN_IN;
  const uint8_t glow = JH_HW_NODE_GLOW_PLUG_PIN_IN;
  const bool pump_low = JH_HW_NODE_PUMP_PULSE_PROP_ACTIVE_LOW;
  const bool glow_low = JH_HW_NODE_GLOW_PLUG_PROP_ACTIVE_LOW;
  levels[pump] = pump_low;
  levels[glow] = glow_low;
  sensorsInit();
  assert(modes[pump] == JH_HW_NODE_PUMP_PULSE_INPUT_MODE);
  assert(modes[glow] == JH_HW_NODE_GLOW_PLUG_INPUT_MODE);
  assert(!sensors.pump_state && !sensors.glow_state);
  assert(callbacks[pump] && callbacks[glow]);

  levels[pump] = !pump_low;
  levels[glow] = !glow_low;
  now_us = 2000;
  callbacks[pump]();
  callbacks[glow]();
  assert(sensors.pump_state && sensors.glow_state);
  assert(sensors.pump_pulse_count == 1);
  assert(event_queue_head == 2);
  assert(event_queue[0].state == 1 && event_queue[1].state == 1);
  callbacks[pump]();
  callbacks[glow]();
  assert(event_queue_head == 2); // repeated IRQ without an edge is ignored

  now_us = 7000;
  levels[pump] = pump_low;
  levels[glow] = glow_low;
  callbacks[pump]();
  callbacks[glow]();
  assert(!sensors.pump_state && !sensors.glow_state);
  assert(sensors.pump_on_duration_ms == 5 && sensors.glow_on_duration_ms == 5);
  assert(event_queue_head == 4);
  assert(event_queue[2].state == 0 && event_queue[3].state == 0);

  // Initial sampling uses the same polarity as subsequent interrupts.
  levels[pump] = !pump_low;
  levels[glow] = !glow_low;
  sensorsInit();
  assert(sensors.pump_state && sensors.glow_state);
  assert(sensors.pump_on_us == now_us && sensors.glow_on_us == now_us);
}
