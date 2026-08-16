import asyncio
import contextlib
import sys
import time


def apply_windows_storage_patch():
    """Monkey-patch NiceGUI's FilePersistentDict to handle WinError 5 Access Denied.

    On Windows, rapid writes to storage files (like user.json) can trigger AV or
    OS file locks, causing os.replace to fail with PermissionError. This patch
    adds a small retry loop around the replace operation.
    """
    if sys.platform != 'win32':
        return

    try:
        import aiofiles
        from nicegui import background_tasks, core
        from nicegui.helpers import unlink_with_retry, unlink_with_retry_async
        from nicegui.persistence.file_persistent_dict import FilePersistentDict
        from nicegui.persistence.serialization import dumps
    except ImportError:
        return

    def _patched_backup(self) -> None:
        """Back up the data to the given file path with retry logic."""
        if not self.filepath.exists():
            if not self:
                return
            self.filepath.parent.mkdir(exist_ok=True)

        tmp_filepath = self.filepath.with_name(self.filepath.name + '.tmp')

        @background_tasks.await_on_shutdown
        async def async_backup() -> None:
            if not self:
                tmp_filepath.unlink(missing_ok=True)
                await unlink_with_retry_async(self.filepath, missing_ok=True)
                return
            async with aiofiles.open(tmp_filepath, 'w', encoding=self.encoding) as f:
                await f.write(dumps(self, str(self.filepath), indent=self.indent))

            with contextlib.suppress(FileNotFoundError):
                retries = 5
                for attempt in range(retries):
                    try:
                        tmp_filepath.replace(self.filepath)
                        break
                    except PermissionError:
                        if attempt == retries - 1:
                            raise
                        await asyncio.sleep(0.05)

        if core.is_loop_running():
            background_tasks.create_lazy(async_backup(), name=self.filepath.stem)
        elif not self:
            tmp_filepath.unlink(missing_ok=True)
            unlink_with_retry(self.filepath, missing_ok=True)
        else:
            tmp_filepath.write_text(
                dumps(self, str(self.filepath), indent=self.indent), encoding=self.encoding
            )
            retries = 5
            for attempt in range(retries):
                try:
                    tmp_filepath.replace(self.filepath)
                    break
                except PermissionError:
                    if attempt == retries - 1:
                        raise
                    time.sleep(0.05)

    FilePersistentDict.backup = _patched_backup
