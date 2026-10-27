"""Byte integrity and failure gates, entirely offline."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from document_trial.transfer import prepare,assemble


class TransferTests(unittest.TestCase):
    def test_default_fragments_are_at_most_one_mib(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root=Path(tmp);src=root/'source.zip';src.write_bytes(b'x'*(1048576+17))
            m=prepare(src,root/'parts','b'*32,str(root/'rebuilt.zip'))
            self.assertEqual([p['bytes'] for p in m['parts']],[1048576,17])

    def setup_files(self,root):
        src=root/'source.zip';src.write_bytes(bytes((i//256)%256 for i in range(1792)))
        m=prepare(src,root/'parts','a'*32,str(root/'rebuilt.zip'),chunk_bytes=512)
        for part in m['parts']:part['remote']=part['local']
        return src,m

    def test_fragments_reconstruct_identical_bytes_and_marker(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            src,m=self.setup_files(Path(tmp))
            with contextlib.redirect_stdout(io.StringIO()) as out:assemble(m)
            self.assertEqual(Path(m['target']).read_bytes(),src.read_bytes())
            self.assertIn('TRANSFER_VERIFIED '+m['sha256'],out.getvalue())

    def test_corrupt_missing_reordered_and_wrong_total_never_publish(self):
        for case in ('corrupt','missing','reordered','total'):
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
                src,m=self.setup_files(Path(tmp))
                if case=='corrupt':Path(m['parts'][0]['local']).write_bytes(b'bad')
                if case=='missing':Path(m['parts'][0]['local']).unlink()
                if case=='reordered':m['parts']=m['parts'][-1:]+m['parts'][:-1]
                if case=='total':m['bytes']+=1
                with self.assertRaises((ValueError,FileNotFoundError)):assemble(m)
                self.assertFalse(Path(m['target']).exists())

    def test_existing_target_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            src,m=self.setup_files(Path(tmp));target=Path(m['target']);target.write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):assemble(m)
            self.assertEqual(target.read_bytes(),b'preserve')

if __name__=='__main__':unittest.main()
