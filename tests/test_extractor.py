import os
import zipfile

import pytest

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from dicom_exporter.extractor import extract_from_zip


def _create_dummy_dicom(path: str) -> None:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(path, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.PatientName = "Test^Patient"
    ds.PatientID = "12345"
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.save_as(path)


def test_extract_single_dicom(tmp_path):
    # create a dicom file and a non-dicom file inside a zip
    dicom_file = tmp_path / "image1.dcm"
    _create_dummy_dicom(str(dicom_file))

    non_dicom = tmp_path / "readme.txt"
    non_dicom.write_text("not a dicom")

    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dicom_file, arcname="image1.dcm")
        zf.write(non_dicom, arcname="readme.txt")

    out_dir = tmp_path / "out"
    extracted = extract_from_zip(str(zip_path), str(out_dir))
    assert len(extracted) == 1
    assert os.path.exists(extracted[0])
    assert extracted[0].endswith("image1.dcm")
