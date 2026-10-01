import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from levelnet.errors import LevelNetError
from levelnet.model import read_control_points, read_observations


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


OBS_HEADER = "id,from,to,dh,sd\n"


class ObservationCsvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_parse(self) -> None:
        path = write(
            self.dir / "obs.csv",
            OBS_HEADER + "o1, A , B ,1.5,0.01\n",
        )
        observations = read_observations(path)
        self.assertEqual(len(observations), 1)
        obs = observations[0]
        self.assertEqual((obs.obs_id, obs.start, obs.end), ("o1", "A", "B"))
        self.assertEqual(obs.dh, 1.5)
        self.assertEqual(obs.sd, 0.01)

    def test_duplicate_id_reports_line(self) -> None:
        path = write(
            self.dir / "obs.csv",
            OBS_HEADER
            + "o1,A,B,1,0.1\n"
            + "o2,B,C,1,0.1\n"
            + "o1,C,A,1,0.1\n",
        )
        with self.assertRaisesRegex(LevelNetError, "第 4 行.*'o1'.*重复"):
            read_observations(path)

    def test_same_start_end(self) -> None:
        path = write(self.dir / "obs.csv", OBS_HEADER + "o1,A,A,1,0.1\n")
        with self.assertRaisesRegex(LevelNetError, "起点与终点相同"):
            read_observations(path)

    def test_nonpositive_sd(self) -> None:
        path = write(self.dir / "obs.csv", OBS_HEADER + "o1,A,B,1,0\n")
        with self.assertRaisesRegex(LevelNetError, "标准差必须为正数"):
            read_observations(path)

    def test_non_finite_values(self) -> None:
        path = write(self.dir / "obs.csv", OBS_HEADER + "o1,A,B,inf,0.1\n")
        with self.assertRaisesRegex(LevelNetError, "必须有限"):
            read_observations(path)

    def test_unparseable_float(self) -> None:
        path = write(self.dir / "obs.csv", OBS_HEADER + "o1,A,B,x,0.1\n")
        with self.assertRaisesRegex(LevelNetError, "无法解析为数值"):
            read_observations(path)

    def test_missing_column(self) -> None:
        path = write(
            self.dir / "obs.csv", "id,from,to,dh\no1,A,B,1\n"
        )
        with self.assertRaisesRegex(LevelNetError, "表头缺少列 sd"):
            read_observations(path)

    def test_empty_file_rows(self) -> None:
        path = write(self.dir / "obs.csv", OBS_HEADER)
        with self.assertRaisesRegex(LevelNetError, "至少需要一条观测"):
            read_observations(path)


class ControlJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid(self) -> None:
        path = self.dir / "c.json"
        write(path, json.dumps({"A": 10.0, "B": 20}))
        controls = read_control_points(path)
        self.assertEqual(controls, {"A": 10.0, "B": 20.0})

    def test_bad_json_reports_position(self) -> None:
        path = write(self.dir / "c.json", "{\"A\": 10,\n broken}")
        with self.assertRaisesRegex(LevelNetError, "JSON 解析失败.*行.*列"):
            read_control_points(path)

    def test_non_object(self) -> None:
        path = write(self.dir / "c.json", "[1, 2]")
        with self.assertRaisesRegex(LevelNetError, "JSON 对象"):
            read_control_points(path)

    def test_non_finite_height(self) -> None:
        path = write(self.dir / "c.json", '{"A": NaN}')
        with self.assertRaises(LevelNetError):
            read_control_points(path)


if __name__ == "__main__":
    unittest.main()
