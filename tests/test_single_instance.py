from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from bookledger.services.single_instance import (
    LibraryAlreadyRunning,
    LibraryInstanceLock,
    LibraryLockError,
)


def _start_holder(library_root: Path) -> subprocess.Popen[str]:
    code = textwrap.dedent(
        """
        import sys
        import time
        from bookledger.services.single_instance import LibraryInstanceLock
        lock = LibraryInstanceLock(sys.argv[1])
        print("READY", flush=True)
        time.sleep(60)
        """
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(library_root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "READY"
    return process


def test_first_instance_and_duplicate_path_alias(tmp_path):
    library_root = tmp_path / "BookLedger"
    library_root.mkdir()
    lock = LibraryInstanceLock(library_root)
    try:
        equivalent = Path(str(library_root / "nested" / ".." / ".").swapcase())
        with pytest.raises(LibraryAlreadyRunning):
            LibraryInstanceLock(equivalent)
    finally:
        lock.close()


def test_independent_libraries_can_be_open_at_once(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    first = LibraryInstanceLock(tmp_path / "one")
    second = LibraryInstanceLock(tmp_path / "two")
    second.close()
    first.close()


def test_normal_close_releases_ownership(tmp_path):
    library_root = tmp_path / "library"
    library_root.mkdir()
    lock = LibraryInstanceLock(library_root)
    lock.close()
    replacement = LibraryInstanceLock(library_root)
    replacement.close()


def test_process_termination_releases_ownership(tmp_path):
    library_root = tmp_path / "library"
    library_root.mkdir()
    process = _start_holder(library_root)
    try:
        with pytest.raises(LibraryAlreadyRunning):
            LibraryInstanceLock(library_root)
        process.terminate()
        process.wait(timeout=10)
        replacement = LibraryInstanceLock(library_root)
        replacement.close()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def test_simultaneous_processes_have_one_owner(tmp_path):
    library_root = tmp_path / "library"
    library_root.mkdir()
    gate = tmp_path / "start"
    code = textwrap.dedent(
        """
        import sys
        import time
        from pathlib import Path
        from bookledger.services.single_instance import LibraryAlreadyRunning, LibraryInstanceLock
        print("READY", flush=True)
        gate = Path(sys.argv[2])
        while not gate.exists():
            time.sleep(.005)
        try:
            lock = LibraryInstanceLock(sys.argv[1])
        except LibraryAlreadyRunning:
            print("BUSY", flush=True)
        else:
            print("OWNER", flush=True)
            time.sleep(.5)
            lock.close()
        """
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(library_root), str(gate)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    try:
        for process in processes:
            assert process.stdout is not None
            assert process.stdout.readline().strip() == "READY"
        gate.touch()
        results = [process.communicate(timeout=15) for process in processes]
        assert all(process.returncode == 0 for process in processes)
        assert sorted(stdout.strip().splitlines()[-1] for stdout, _stderr in results) == ["BUSY", "OWNER"]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


def test_lock_open_failure_is_reported(monkeypatch, tmp_path):
    import bookledger.services.single_instance as single_instance

    class FakeFunction:
        argtypes = None
        restype = None

        def __init__(self, function):
            self.function = function

        def __call__(self, *args):
            return self.function(*args)

    class FakeKernel32:
        CreateFileW = FakeFunction(lambda *_args: fail_create())
        CloseHandle = FakeFunction(lambda *_args: 1)

    def fail_create():
        single_instance.ctypes.set_last_error(5)
        return None

    monkeypatch.setattr(single_instance.ctypes, "WinDLL", lambda *_args, **_kwargs: FakeKernel32())
    with pytest.raises(LibraryLockError, match="Windows error 5"):
        LibraryInstanceLock(tmp_path)


def test_main_holds_lock_through_window_and_releases_after_startup_error(monkeypatch, tmp_path):
    import bookledger.app as app_module

    paths = type("Paths", (), {"root": tmp_path, "database": tmp_path / "data" / "bookledger.sqlite3"})()
    monkeypatch.setattr(app_module, "AppPaths", lambda: paths)

    class StartupFailure:
        def __init__(self, supplied_paths):
            assert supplied_paths is paths
            with pytest.raises(LibraryAlreadyRunning):
                LibraryInstanceLock(paths.root)
            raise RuntimeError("startup failed")

    monkeypatch.setattr(app_module, "BookLedgerApp", StartupFailure)
    with pytest.raises(RuntimeError, match="startup failed"):
        app_module.main()

    replacement = LibraryInstanceLock(paths.root)
    replacement.close()


def test_main_holds_lock_through_event_loop_and_releases_on_close(monkeypatch, tmp_path):
    import bookledger.app as app_module

    paths = type("Paths", (), {"root": tmp_path, "database": tmp_path / "data" / "bookledger.sqlite3"})()
    monkeypatch.setattr(app_module, "AppPaths", lambda: paths)

    class RunningApp:
        def __init__(self, supplied_paths):
            assert supplied_paths is paths

        def mainloop(self):
            with pytest.raises(LibraryAlreadyRunning):
                LibraryInstanceLock(paths.root)

    monkeypatch.setattr(app_module, "BookLedgerApp", RunningApp)
    assert app_module.main() == 0
    replacement = LibraryInstanceLock(paths.root)
    replacement.close()


def test_main_notifies_and_exits_on_duplicate(monkeypatch, tmp_path):
    import bookledger.app as app_module

    paths = type("Paths", (), {"root": tmp_path, "database": tmp_path / "data" / "bookledger.sqlite3"})()
    owner = LibraryInstanceLock(paths.root)
    notices = []
    monkeypatch.setattr(app_module, "AppPaths", lambda: paths)
    monkeypatch.setattr(app_module, "_show_startup_message", lambda message, **kwargs: notices.append((message, kwargs)))
    monkeypatch.setattr(app_module, "BookLedgerApp", lambda *_args: pytest.fail("duplicate must not initialize the UI"))
    try:
        assert app_module.main() == 0
    finally:
        owner.close()
    assert notices and "already open" in notices[0][0]
    assert notices[0][1] == {"warning": True}


def test_main_fails_closed_when_lock_cannot_be_created(monkeypatch, tmp_path):
    import bookledger.app as app_module

    paths = type("Paths", (), {"root": tmp_path, "database": tmp_path / "data" / "bookledger.sqlite3"})()
    notices = []
    monkeypatch.setattr(app_module, "AppPaths", lambda: paths)
    monkeypatch.setattr(app_module, "LibraryInstanceLock", lambda *_args: (_ for _ in ()).throw(LibraryLockError("access denied")))
    monkeypatch.setattr(app_module, "_show_startup_message", lambda message, **kwargs: notices.append(message))
    monkeypatch.setattr(app_module, "BookLedgerApp", lambda *_args: pytest.fail("lock failure must not initialize the UI"))
    assert app_module.main() == 1
    assert notices and "will not start" in notices[0]
