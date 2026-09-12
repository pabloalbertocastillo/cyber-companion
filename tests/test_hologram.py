"""The ambient readouts must never display stale readings as current."""
import unittest
from cyber_companion.ui.hologram import telemetry, anatomy_scale


class TelemetryTests(unittest.TestCase):
    def test_missing_and_stale_are_unknown_not_zero_or_disconnected(self):
        for snap in (None, {}, {'domains': {'system': {'fresh': False, 'value': {'cpu_ratio': .9}},
                                          'network': {'fresh': False, 'value': {'default_route': False}}}}):
            result = telemetry(snap)
            self.assertIsNone(result['cpu'])
            self.assertIsNone(result['memory'])
            self.assertEqual(result['network'], 'NET —')
            self.assertIsNone(result['route'])
            self.assertIsNone(result['temperature_limit'])

    def test_anatomy_size_is_bounded_and_reduced_motion_is_stable(self):
        low = telemetry(None)
        high = dict(low,cpu=1.,memory=1.)
        self.assertLess(anatomy_scale(low),anatomy_scale(high))
        self.assertLessEqual(anatomy_scale(high,hovered=True),1.13)
        self.assertGreaterEqual(anatomy_scale(low),.90)
        self.assertEqual(anatomy_scale(low,reduced=True),anatomy_scale(high,hovered=True,reduced=True))

    def test_live_readings_storage_pressure_and_vm_activity(self):
        values = {'system': {'cpu_ratio': .2, 'memory_ratio': .4},
                  'network': {'default_route': False},
                  'media': {'status': 'playing'},
                  'storage': {'mounts': [dict(path='/', ratio=.4), dict(path='/home', ratio=.05)]},
                  'virtualization': {'vms': [dict(state='running'), dict(state='shut off')]}}
        result = telemetry({'domains': {k: {'fresh': True, 'value': v} for k, v in values.items()}})
        self.assertEqual(result['cpu'], .2)
        self.assertEqual(result['network'], 'NO ROUTE')
        self.assertTrue(result['media'])
        self.assertEqual(result['storage']['path'], '/home')
        self.assertEqual(result['running_vms'], 1)


if __name__ == '__main__':
    unittest.main()
