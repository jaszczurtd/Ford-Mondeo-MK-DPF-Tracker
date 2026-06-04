#pragma once

/**
 * @file hal_project_config.h
 * @brief JaszczurHAL module configuration for the Mondeo DPF Tracker project.
 *
 * This file is automatically picked up by hal_config.h via __has_include.
 * Define HAL_DISABLE_* flags here to exclude unused HAL modules from the
 * build.  Dependency propagation (e.g. EEPROM → KV) is handled by
 * hal_config.h — you only need to disable the base module.
 */

/* ── Modules not used by Mondeo DPF Tracker ──────────────────────────────────────── */

#define HAL_ENABLE_CJSON            /* cJSON JSON parser                    */
#define HAL_ENABLE_THERMOCOUPLE        /* Thermocouple driver (MCP9600)         */
#define HAL_ENABLE_MCP9600            /* MCP9600 thermocouple amplifier        */
#define HAL_ENABLE_UART               /* UART serial communication              */
#define HAL_ENABLE_RGB_LED            /* RGB LED driver (NeoPixel)              */
#define HAL_ENABLE_A7670              /* SimCom A76xx cellular modem driver     */
                                      /* (auto-enables HAL_ENABLE_CELLULAR_MODEM
                                         and HAL_ENABLE_UART)                   */
