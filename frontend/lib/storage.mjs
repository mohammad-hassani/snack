// Keep drafts and channel preferences created before the Snack rename.
export function migrateStorage(storage) {
  for (const key of Object.keys(storage)) {
    if (!key.startsWith("teamflow:") && !key.startsWith("teamflow-channel:"))
      continue;
    const renamed = key.replace(/^teamflow/, "snack");
    if (storage.getItem(renamed) !== null) continue;
    storage.setItem(renamed, storage.getItem(key));
    storage.removeItem(key);
  }
}
