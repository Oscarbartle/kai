//! The desktop half of "Export data" (Settings → Backup).
//!
//! The server builds the zip (`GET /export` — see `crates/kai-server`'s
//! `routes/export.rs` for what is in it); this side downloads it and saves
//! it into the user's Downloads folder under a timestamped name. Server
//! only, on purpose: the app's own local SQLite data is not covered.

use chrono::{DateTime, Local};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};

/// `kai-backup-2026-10-06_14-32-05.zip`, in the *user's* local time (what
/// they would expect to see in their Downloads folder).
pub fn backup_filename(now: DateTime<Local>) -> String {
    format!("kai-backup-{}.zip", now.format("%Y-%m-%d_%H-%M-%S"))
}

/// Fetches the export zip from the shared server.
pub async fn download_backup(base_url: &str, token: &str) -> Result<Vec<u8>, String> {
    let url = base_url.trim_end_matches('/');
    let resp = reqwest::Client::new()
        .get(format!("{url}/export"))
        .bearer_auth(token)
        .send()
        .await
        .map_err(|e| format!("Couldn't reach {url}: {e}"))?;

    let status = resp.status();
    if status == reqwest::StatusCode::UNAUTHORIZED {
        return Err("The server rejected the token".to_string());
    }
    // A server from before the export existed has no /export route; its
    // static-file handler answers that with 404 or 405. Say what to do
    // rather than showing a bare status code.
    if status == reqwest::StatusCode::NOT_FOUND || status == reqwest::StatusCode::METHOD_NOT_ALLOWED {
        return Err("This server is too old to export — update it, then try again".to_string());
    }
    if !status.is_success() {
        return Err(format!("Server responded with {status}"));
    }

    let bytes = resp
        .bytes()
        .await
        .map_err(|e| format!("The download was interrupted: {e}"))?;
    // Every zip starts with "PK" — a proxy's HTML error page that still
    // said 200 must not be saved as if it were a backup.
    if !bytes.starts_with(b"PK") {
        return Err("The server didn't send a zip file".to_string());
    }
    Ok(bytes.to_vec())
}

/// Writes `bytes` to `dir/name`, never overwriting: if that name is taken
/// it becomes `name-2.zip`, `name-3.zip`, … Returns the path used.
pub fn write_unique(dir: &Path, name: &str, bytes: &[u8]) -> Result<PathBuf, String> {
    std::fs::create_dir_all(dir).map_err(|e| format!("Couldn't create {}: {e}", dir.display()))?;
    let (stem, ext) = match name.rsplit_once('.') {
        Some((stem, ext)) => (stem, format!(".{ext}")),
        None => (name, String::new()),
    };
    for attempt in 1..=1000 {
        let candidate = if attempt == 1 {
            name.to_string()
        } else {
            format!("{stem}-{attempt}{ext}")
        };
        let path = dir.join(&candidate);
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(mut file) => {
                file.write_all(bytes)
                    .map_err(|e| format!("Couldn't write {}: {e}", path.display()))?;
                return Ok(path);
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(format!("Couldn't save {}: {e}", path.display())),
        }
    }
    Err(format!("Couldn't find a free file name for {name} in {}", dir.display()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn filename_is_sortable_local_time_to_the_second() {
        let t = Local.with_ymd_and_hms(2026, 10, 6, 14, 32, 5).unwrap();
        assert_eq!(backup_filename(t), "kai-backup-2026-10-06_14-32-05.zip");
    }

    #[test]
    fn never_overwrites_an_existing_backup() {
        let dir = std::env::temp_dir().join(format!("kai-backup-test-{}", std::process::id()));
        std::fs::remove_dir_all(&dir).ok();

        let first = write_unique(&dir, "kai-backup-x.zip", b"one").unwrap();
        let second = write_unique(&dir, "kai-backup-x.zip", b"two").unwrap();
        let third = write_unique(&dir, "kai-backup-x.zip", b"three").unwrap();
        assert_eq!(first.file_name().unwrap(), "kai-backup-x.zip");
        assert_eq!(second.file_name().unwrap(), "kai-backup-x-2.zip");
        assert_eq!(third.file_name().unwrap(), "kai-backup-x-3.zip");
        assert_eq!(std::fs::read(&first).unwrap(), b"one", "the original must be untouched");
        assert_eq!(std::fs::read(&second).unwrap(), b"two");

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn creates_the_folder_if_needed() {
        let dir = std::env::temp_dir()
            .join(format!("kai-backup-test-nested-{}", std::process::id()))
            .join("a")
            .join("b");
        let path = write_unique(&dir, "f.zip", b"x").unwrap();
        assert!(path.exists());
        std::fs::remove_dir_all(dir.parent().unwrap().parent().unwrap()).ok();
    }
}
