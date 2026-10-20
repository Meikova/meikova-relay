import unittest
from typing import Tuple, Dict, Any, List

class MultiMonitorHelper:
    """Helper functions for multi-monitor slice calculation and coordinate translation."""

    @staticmethod
    def calculate_monitor_slice(
        mon_rect: Tuple[int, int, int, int],
        virtual_screen: Tuple[int, int, int, int]
    ) -> Tuple[int, int, int, int]:
        """
        Calculates the sub-rectangle (sx, sy, sw, sh) of a monitor within the virtual desktop bitmap.
        mon_rect: (left, top, right, bottom)
        virtual_screen: (vx, vy, vw, vh)
        """
        m_left, m_top, m_right, m_bottom = mon_rect
        vx, vy, vw, vh = virtual_screen

        sx = max(0, m_left - vx)
        sy = max(0, m_top - vy)
        sw = max(1, m_right - m_left)
        sh = max(1, m_bottom - m_top)
        return (sx, sy, sw, sh)

    @staticmethod
    def map_normalized_to_monitor_pixel(
        norm_x: float,
        norm_y: float,
        mon_rect: Tuple[int, int, int, int]
    ) -> Tuple[int, int]:
        """
        Maps normalized (0.0..1.0) coordinates within a specific monitor to absolute desktop pixels (px, py).
        """
        m_left, m_top, m_right, m_bottom = mon_rect
        clamped_x = max(0.0, min(1.0, float(norm_x)))
        clamped_y = max(0.0, min(1.0, float(norm_y)))

        px = int(round(m_left + clamped_x * (m_right - m_left)))
        py = int(round(m_top + clamped_y * (m_bottom - m_top)))
        return (px, py)


class TestMultiMonitorGrid(unittest.TestCase):
    def test_dual_monitor_side_by_side_slices(self):
        # Mon 1: 1920x1080 at (0, 0, 1920, 1080)
        # Mon 2: 1920x1080 at (1920, 0, 3840, 1080)
        # Virtual desktop: (0, 0, 3840, 1080)
        v_screen = (0, 0, 3840, 1080)
        m1 = (0, 0, 1920, 1080)
        m2 = (1920, 0, 3840, 1080)

        s1 = MultiMonitorHelper.calculate_monitor_slice(m1, v_screen)
        s2 = MultiMonitorHelper.calculate_monitor_slice(m2, v_screen)

        self.assertEqual(s1, (0, 0, 1920, 1080))
        self.assertEqual(s2, (1920, 0, 1920, 1080))

    def test_dual_monitor_negative_offset_slice(self):
        # Secondary monitor to the left: (-1920, 0, 0, 1080)
        # Primary monitor: (0, 0, 1920, 1080)
        # Virtual desktop: vx=-1920, vy=0, vw=3840, vh=1080
        v_screen = (-1920, 0, 3840, 1080)
        m_left = (-1920, 0, 0, 1080)
        m_right = (0, 0, 1920, 1080)

        s_left = MultiMonitorHelper.calculate_monitor_slice(m_left, v_screen)
        s_right = MultiMonitorHelper.calculate_monitor_slice(m_right, v_screen)

        self.assertEqual(s_left, (0, 0, 1920, 1080))
        self.assertEqual(s_right, (1920, 0, 1920, 1080))

    def test_vertical_stacked_slices(self):
        # Mon 1: (0, 0, 1920, 1080)
        # Mon 2: (0, 1080, 1920, 2160)
        # Virtual screen: (0, 0, 1920, 2160)
        v_screen = (0, 0, 1920, 2160)
        m1 = (0, 0, 1920, 1080)
        m2 = (0, 1080, 1920, 2160)

        s1 = MultiMonitorHelper.calculate_monitor_slice(m1, v_screen)
        s2 = MultiMonitorHelper.calculate_monitor_slice(m2, v_screen)

        self.assertEqual(s1, (0, 0, 1920, 1080))
        self.assertEqual(s2, (0, 1080, 1920, 1080))

    def test_coordinate_mapping_accuracy(self):
        m1 = (0, 0, 1920, 1080)
        m2 = (1920, 0, 3840, 1080)

        # Center of Mon 1
        px1, py1 = MultiMonitorHelper.map_normalized_to_monitor_pixel(0.5, 0.5, m1)
        self.assertEqual((px1, py1), (960, 540))

        # Center of Mon 2
        px2, py2 = MultiMonitorHelper.map_normalized_to_monitor_pixel(0.5, 0.5, m2)
        self.assertEqual((px2, py2), (2880, 540))

        # Bottom-right of Mon 2
        px_br, py_br = MultiMonitorHelper.map_normalized_to_monitor_pixel(1.0, 1.0, m2)
        self.assertEqual((px_br, py_br), (3840, 1080))


if __name__ == "__main__":
    unittest.main()
