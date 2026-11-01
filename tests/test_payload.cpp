// Test the JSON number helper of the production payload.
#include "../tracker.cpp"
#include <cassert>
#include <cstring>

extern "C" {
void hal_deb(const char *, ...) {}
void hal_derr(const char *, ...) {}
}

// The printed object, which must parse back as JSON.
static cJSON *roundTrip(cJSON *root) {
  char *text = cJSON_PrintUnformatted(root);
  assert(text != nullptr);
  cJSON *parsed = cJSON_Parse(text);
  assert(parsed != nullptr);
  cJSON_free(text);
  return parsed;
}

int main() {
  cJSON *root = cJSON_CreateObject();
  assert(addFixed2Number(root, "egt_pre", NAN) != nullptr);
  assert(addFixed2Number(root, "egt_mid", INFINITY) != nullptr);
  assert(addFixed2Number(root, "mcu_temp", 312.456f) != nullptr);

  cJSON *parsed = roundTrip(root);
  assert(cJSON_IsNull(cJSON_GetObjectItem(parsed, "egt_pre")));
  assert(cJSON_IsNull(cJSON_GetObjectItem(parsed, "egt_mid")));
  const cJSON *temp = cJSON_GetObjectItem(parsed, "mcu_temp");
  assert(cJSON_IsNumber(temp));
  assert(fabs(temp->valuedouble - 312.46) < 1e-6);

  cJSON_Delete(parsed);
  cJSON_Delete(root);
  return 0;
}
