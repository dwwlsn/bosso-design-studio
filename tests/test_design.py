import asyncio
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

spec = importlib.util.spec_from_file_location("design", Path(__file__).resolve().parents[1] / "custom_components/bosso_studio/design.py")
design = importlib.util.module_from_spec(spec)
spec.loader.exec_module(design)


class Disk:
    def __init__(self, path):
        self.path = path

    async def async_save(self, data):
        self.path.write_text(json.dumps(data))


class Tests(unittest.IsolatedAsyncioTestCase):
    def test_preview(self):
        self.assertEqual(design.compile_strip(["#ff0000","#0000ff"],5,[dict(first=3,last=4,colors=["#ffffff"])]),
                         ["#FF0000","#0000FF","#FFFFFF","#FFFFFF","#FF0000"])

    def test_invalid(self):
        for palette, count, sections in [([],5,[]), (["bad"],5,[]), (["#ffffff"],0,[]),
                (["#ffffff"],1,[dict(first=1,last=2,colors=["#ffffff"])])]:
            with self.assertRaises(ValueError):
                design.compile_strip(palette,count,sections)

    async def test_restart_conflict_rollback(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)/"designs.json"
            lib = design.Library(Disk(path),{})
            record = {"colors":["#ff0000"]}
            results = await asyncio.gather(lib.save("sample",0,record),lib.save("sample",0,record),return_exceptions=True)
            self.assertEqual(sum(isinstance(r,ValueError) for r in results),1)
            await lib.save("sample",1,{"colors":["#0000ff"]})
            new_client = design.Library(Disk(path),json.loads(path.read_text()))
            self.assertEqual(new_client.get("sample",1)["colors"],record["colors"])
            self.assertEqual(new_client.get("sample")["revision"],2)
            new_client.storage = Disk(Path(temp)/"missing"/"file")
            with self.assertRaises(OSError):
                await new_client.save("sample",2,record)
            self.assertEqual(new_client.get("sample")["revision"],2)


if __name__ == "__main__":
    unittest.main()


