import os
import time
import threading

def cleanup_temp_files(temp_folder, max_age_seconds=3600):
    """
    Deletes files in temp_folder that have not been modified for max_age_seconds (default 1 hour = 3600s).
    Returns statistics on deleted files.
    """
    if not temp_folder or not os.path.exists(temp_folder):
        return {"deleted_count": 0, "freed_bytes": 0, "errors": []}

    now = time.time()
    deleted_count = 0
    freed_bytes = 0
    errors = []

    try:
        for filename in os.listdir(temp_folder):
            filepath = os.path.join(temp_folder, filename)
            if os.path.isfile(filepath):
                try:
                    file_age = now - os.path.getmtime(filepath)
                    if file_age > max_age_seconds:
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        deleted_count += 1
                        freed_bytes += file_size
                        print(f"[Temp Cleaner] Removed old temp file '{filename}' (Age: {int(file_age // 60)} mins, Size: {file_size} bytes)")
                except Exception as fe:
                    errors.append(f"Failed to delete {filename}: {str(fe)}")
    except Exception as e:
        errors.append(f"Error scanning temp directory: {str(e)}")

    return {"deleted_count": deleted_count, "freed_bytes": freed_bytes, "errors": errors}


def start_periodic_temp_cleaner(temp_folder, max_age_seconds=3600, interval_seconds=900):
    """
    Launches a daemon background thread that runs cleanup_temp_files periodically every interval_seconds (default 15 minutes).
    """
    def _worker():
        # Run immediate cleanup on thread start
        try:
            cleanup_temp_files(temp_folder, max_age_seconds=max_age_seconds)
        except Exception as e:
            print(f"[Temp Cleaner Start Error]: {e}")

        while True:
            time.sleep(interval_seconds)
            try:
                cleanup_temp_files(temp_folder, max_age_seconds=max_age_seconds)
            except Exception as e:
                print(f"[Temp Cleaner Worker Error]: {e}")

    cleaner_thread = threading.Thread(target=_worker, daemon=True, name="TempFileCleanerThread")
    cleaner_thread.start()
    print(f"[Temp Cleaner] Periodic background cleaner started for folder '{temp_folder}' (Purging files > {max_age_seconds // 3600}h every {interval_seconds // 60}m)")
    return cleaner_thread
