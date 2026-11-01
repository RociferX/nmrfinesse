"""Copy project UCSF results without losing source files or destination content."""

from pathlib import Path

from core.project import ProjectManager
from workflow.ucsf_transfer import transfer_ucsf_files, ucsf_export_entries


def test_catalog_uses_current_spectrum_and_excludes_trashed_data(tmp_path):
    manager = ProjectManager.create_project(tmp_path / 'project', 'demo')
    exp = manager.create_experiment('HSQC')
    data = manager.import_data(exp.id, tmp_path / 'raw')
    directory = manager.data_dir(exp.id, data.id, 'spectra')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'old.ucsf').write_bytes(b'old')
    (directory / 'current.ucsf').write_bytes(b'current')
    data.spectrum_path = (directory / 'current.ft2').relative_to(manager.root).as_posix()
    other = manager.import_data(exp.id, tmp_path / 'other')
    entries = ucsf_export_entries(manager)
    assert Path(entries[0]['source']).read_bytes() == b'current'
    assert entries[1]['source'] == ''
    other.trashed = True
    assert len(ucsf_export_entries(manager)) == 1
    exp.trashed = True
    assert ucsf_export_entries(manager) == []


def test_transfer_preserves_sources_and_handles_duplicate_and_existing_names(tmp_path):
    source = tmp_path / 'data.ucsf'
    source.write_bytes(b'UCSF spectrum' * 1000)
    entry = dict(source=str(source), project='demo', experiment='HSQC', data='sample')
    destination = tmp_path / 'exports'
    destination.mkdir()
    previous = destination / 'demo_HSQC_sample.ucsf'
    previous.write_bytes(b'existing spectrum')
    result = transfer_ucsf_files([entry, entry], destination)
    assert not result['errors']
    assert len(set(result['copied'])) == 2
    assert previous.read_bytes() == b'existing spectrum'
    assert all(Path(path).read_bytes() == source.read_bytes() for path in result['copied'])
    assert source.is_file()


def test_transfer_reports_missing_files_and_keeps_successful_copies(tmp_path):
    source = tmp_path / 'data.ucsf'
    source.write_bytes(b'spectrum')
    entry = dict(source=str(source), project='demo', experiment='A/B', data='sample')
    missing = {**entry, 'source': str(tmp_path / 'missing.ucsf')}
    result = transfer_ucsf_files([missing, entry], tmp_path / 'exports')
    assert len(result['errors']) == len(result['copied']) == 1
    assert Path(result['copied'][0]).parent == tmp_path / 'exports'
    assert Path(result['copied'][0]).read_bytes() == b'spectrum'
