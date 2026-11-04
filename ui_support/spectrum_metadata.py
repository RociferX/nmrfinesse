"""Qt-free source metadata shared by project and standalone spectrum views."""

from pathlib import Path

from ui_support.i18n import tr


def bruker_title(data, raw_dir: Path | None = None) -> str:
    """Read the original or imported Bruker title without altering the data."""
    source = str(getattr(data, 'source', '') or '')
    roots = [Path(source)] if source else []
    if raw_dir is not None:
        roots.append(raw_dir)
    for root in roots:
        try:
            candidates = [root / 'title']
            pdata = root / 'pdata'
            if pdata.is_dir():
                candidates.extend(p / 'title' for p in sorted(
                    (p for p in pdata.iterdir() if p.is_dir() and p.name.isdigit()),
                    key=lambda p: int(p.name)))
            for path in candidates:
                if path.is_file():
                    raw = path.read_bytes()
                    try:
                        text = raw.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        text = raw.decode('latin-1')
                    if text.strip():
                        return text.replace('\r\n', '\n').replace('\r', '\n').strip()
        except OSError:
            continue
    return ''


def spectrum_tooltip(path: Path | None, manager=None, *, title_formatter=None) -> str:
    """Identify a spectrum by its full path, source and original multiline title."""
    if path is None:
        return ''
    path = Path(path)
    source = tr('Not recorded')
    title = ''
    project = getattr(manager, 'project', None)
    if project is not None:
        for experiment in project.experiments:
            for data in experiment.data or []:
                folder = manager.data_dir(experiment.id, data.id, 'spectra')
                if path.parent.resolve() != folder.resolve():
                    continue
                raw = (manager.root / data.raw_dir if data.raw_dir else
                       manager.data_dir(experiment.id, data.id, 'raw'))
                source = data.source or str(raw)
                if data.segments:
                    source += '\n' + '\n'.join(data.segments)
                title = bruker_title(data, raw)
                break
            else:
                continue
            break
    if not title:
        # Standalone and external spectra can carry a nearby imported title.
        title = bruker_title(None, path.parent)
        if not title and path.parent.name == 'spectra':
            title = bruker_title(None, path.parent.parent / 'raw')
    if title and title_formatter is not None:
        title = title_formatter(title)
    return tr('Spectrum: {p0}\nTitle: {p1}\nOriginal data: {p2}\nSpectrum file: {p3}',
              p0=path.name, p1=title or tr('Not recorded'), p2=source, p3=path)
