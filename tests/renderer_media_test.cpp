#include "platform/update_shared_memory.h"

#include <cassert>

int main() {
  using bongocat::platform::update::update_shared_memory_t;

  update_shared_memory_t state{};
  assert(!state.media_active);
  state.media_active = true;
  assert(state.media_active);
  return 0;
}
