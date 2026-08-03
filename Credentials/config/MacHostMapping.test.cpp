#include "../MacHostMapping.h"

// Locally administered MAC plus RFC 5737 documentation address. These values
// are non-secret and reserved for tests.
const MacEntry mac_table[] = {
    {
        "02:00:00:00:00:01",
        "ci-mondeo-dpf-tracker",
        1,
        "192.0.2.11",
        "ci-example-wireguard-private-key"
    }
};

const size_t mac_table_size = sizeof(mac_table) / sizeof(mac_table[0]);
