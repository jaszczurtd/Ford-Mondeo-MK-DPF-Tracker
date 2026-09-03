#include "../MacHostMapping.h"

#include <hal/core/hal_array.h>

// Copy this file to MacHostMapping.local.cpp and enter the MAC address of your
// board. The private key is returned as a newly allocated string and is erased
// and freed by the Tracker after WireGuard initialization.
const MacEntry mac_table[] = {
    {
        "AA:BB:CC:DD:EE:01",
        "mondeo-dpf-tracker",
        1,
        "10.8.0.11",
        "YOUR_DEVICE_WIREGUARD_PRIVATE_KEY"
    }
};

const size_t mac_table_size = COUNTOF(mac_table);
