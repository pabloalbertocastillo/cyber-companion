import unittest

from cyber_companion.ui.interaction import AmbientVisibility, Output, drag_placement


class DragGeometryTests(unittest.TestCase):
    def setUp(self):
        self.outputs = [Output('left', -1920, 0, 1920, 1080),
                        Output('main', 0, 0, 2560, 1440),
                        Output('above', 0, -1080, 1920, 1080)]
        self.size = (384, 336)

    def place(self, x, y):
        return drag_placement(self.outputs, (x, y), (192, 168), self.size)

    def test_cross_outputs_in_both_axes_without_pixel_scale_conversion(self):
        self.assertEqual(self.place(-600, 400), ('left', 408, 512))
        self.assertEqual(self.place(600, 400), ('main', 1768, 872))
        self.assertEqual(self.place(600, -400), ('above', 1128, 232))
        self.assertEqual(self.place(-1, 500)[0], 'left')
        self.assertEqual(self.place(0, 500)[0], 'main')

    def test_edges_and_gaps_keep_full_character_reachable(self):
        self.assertEqual(self.place(2559, 1439), ('main', 0, 0))
        self.assertEqual(self.place(-1919, 1), ('left', 1536, 744))
        self.assertEqual(self.place(-50, -100)[0], 'above')
        self.assertIsNone(drag_placement([], (0, 0), (0, 0), self.size))
        self.assertEqual(drag_placement([Output('tiny', 0, 0, 300, 200)],
                                       (150, 100), (192, 168), self.size), ('tiny', 0, 0))

    def test_ultrawide_position_is_not_limited_to_2048(self):
        self.assertEqual(drag_placement([Output('wide', 0, 0, 5120, 2160)],
                                       (192, 168), (192, 168), self.size), ('wide', 4736, 1824))


class AmbientTests(unittest.TestCase):
    def test_grace_fade_and_fast_recovery(self):
        visibility = AmbientVisibility(0)
        self.assertEqual(visibility.step(2, .1), 1)
        for i in range(300):
            visibility.step(3+i/60, 1/60)
        self.assertEqual(visibility.opacity, .08)
        for i in range(18):
            visibility.step(8+i/60, 1/60, active=True)
        self.assertGreater(visibility.opacity, .98)
        self.assertEqual(visibility.step(9, 1), 1)

    def test_menu_drag_or_panel_prevent_fading_and_reduced_motion_still_fades(self):
        visibility = AmbientVisibility(0)
        self.assertEqual(visibility.step(100, 1, active=True), 1)
        self.assertEqual(visibility.step(102, 1), 1)
        self.assertEqual(visibility.step(110, .01, reduced=True), .08)
        self.assertEqual(visibility.step(111, .01, active=True, reduced=True), 1)


if __name__ == '__main__':
    unittest.main()
