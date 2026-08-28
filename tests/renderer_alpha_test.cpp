#include "graphics/drawing.h"

#include <array>
#include <cassert>
#include <cstdint>

using bongocat::animation::blit_image_color_option_flags_t;
using bongocat::animation::blit_image_color_order_t;
using bongocat::animation::blit_image_scaled;
using bongocat::animation::drawing_blend_pixel;
using bongocat::animation::drawing_copy_pixel;

int main() {
  constexpr auto normal = blit_image_color_option_flags_t::Normal;
  constexpr auto rgba = blit_image_color_order_t::RGBA;
  constexpr auto bgra = blit_image_color_order_t::BGRA;

  {
    std::array<uint8_t, 4> destination{};
    constexpr std::array<unsigned char, 4> source{100, 200, 50, 128};
    drawing_copy_pixel(destination.data(), 4, 0, source.data(), 4, 0, normal, bgra, rgba);
    assert((destination == std::array<uint8_t, 4>{25, 100, 50, 128}));
  }

  {
    std::array<uint8_t, 4> staging{};
    constexpr std::array<unsigned char, 4> source{100, 200, 50, 128};
    drawing_copy_pixel(staging.data(), 4, 0, source.data(), 4, 0, normal, rgba, rgba);
    assert((staging == source));
  }

  {
    std::array<uint8_t, 4> destination{};
    drawing_blend_pixel(destination.data(), 4, 0, 255, 0, 0, 128, 4, normal, bgra, rgba);
    assert((destination == std::array<uint8_t, 4>{0, 0, 128, 128}));

    drawing_blend_pixel(destination.data(), 4, 0, 0, 0, 255, 128, 4, normal, bgra, rgba);
    assert((destination == std::array<uint8_t, 4>{128, 0, 64, 192}));
  }

  {
    constexpr std::array<unsigned char, 8> source{
        255, 255, 255, 255,
        0, 0, 0, 0,
    };
    std::array<uint8_t, 12> destination{};
    blit_image_scaled(destination.data(), destination.size(), 3, 1, 4, source.data(), source.size(), 2, 1, 4, 0, 0,
                      2, 1, 0, 0, 3, 1, bgra, rgba,
                      blit_image_color_option_flags_t::BilinearInterpolation);
    assert((destination == std::array<uint8_t, 12>{
                               255, 255, 255, 255,
                               85, 85, 85, 85,
                               0, 0, 0, 0,
                           }));
  }

  return 0;
}
