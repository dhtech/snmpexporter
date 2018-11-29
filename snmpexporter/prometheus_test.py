import prometheus
import unittest


class TestBytesToDatetime(unittest.TestCase):
  def testDatetime(self):
    time_data = b'\x07\xE2\x0B\x1D\x0E\x11\x0B\x00+\x00\x00'
    self.assertEqual(prometheus.bytes_to_datetime(time_data), 1543501031.0)


def main():
  unittest.main()


if __name__ == '__main__':
  main()
