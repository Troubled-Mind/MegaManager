# MegaManager Changes

## 1. ✅ Password Update Feature

**Added:** Account password update functionality

**Files Modified:**
- `utils/commands/accounts/account_update_password.py` (NEW)
- `web/accounts.html` - Added update password modal
- `web/scripts/accounts.js` - Added UI functions and dropdown menu item

**Usage:**
1. Go to Accounts page
2. Click the "..." menu next to any account
3. Select "Update Password"
4. Enter the new password
5. Click "Update"

**API:**
- Command: `account:update_password`
- Args format: `account_id:new_password`
- Returns: Success message with email confirmation

---

## 2. 🔧 Local Indexing Issue Fix

**Problem:** Files tab shows no local sizes, uploads fail with "local folder doesn't exist"

**Root Cause:** 
The indexing only processes folders matching configured date formats. If date formats aren't set OR your folders don't match the patterns, they won't be indexed.

### Solution Steps:

#### A. Configure Date Formats (if not already set)

1. Go to **Settings** page
2. Scroll to "Local & Cloud Settings" section
3. Set **at least one** date format pattern:
   - **Full Date Format**: e.g., `%Y-%m-%d` (matches: 2024-09-02)
   - **Month Format**: e.g., `%B %Y` (matches: September 2024)
   - **Year Format**: e.g., `%Y` (matches: 2024)

**Common patterns:**
```
%Y-%m-%d        → 2024-09-02
%Y %m %d        → 2024 09 02
%B %d, %Y       → September 02, 2024
%d-%m-%Y        → 02-09-2024
%Y              → 2024
```

4. **Save Settings**

#### B. Set Local Paths

1. In Settings, configure **Local Paths** (JSON array):
   ```json
   ["/mnt/media", "/home/user/videos"]
   ```
2. These are the root directories to scan

#### C. Run Indexing

1. Go to **Files** page
2. Click **"Index Local"** button
3. Wait for completion (runs in background)
4. Check browser console for:
   ```
   INFO Extracted X root folders.
   Background indexing done. Y new, Z linked, W updated.
   ```

### Still Not Working?

**Check folder structure:**
Your folders must match the date patterns. For example, if you set `%Y-%m-%d`:
```
✅ /mnt/media/2024-09-02/Video.mkv  → Will be indexed
❌ /mnt/media/September-2-2024/Video.mkv  → Won't match
```

**Debug steps:**
1. Open browser DevTools Console
2. Run indexing
3. Look for: `INFO Using full date format: ...` messages
4. If it says `WARNING No date formats configured` → go back to Settings
5. If folders don't match, either:
   - Rename folders to match the pattern, OR
   - Adjust the date format pattern to match your folder names

### Alternative: Force Index All Folders

If you want to index ALL folders regardless of date format, you can modify:
`utils/commands/files/file_local_index.py` line 35:

**Before:**
```python
root_folders = extract_root_dated_folders(all_subfolders)
```

**After:**
```python
# Index all folders instead of only date-formatted ones
root_folders = all_subfolders
```

Then re-run the indexing.

---

## Testing

1. **Password Update:**
   - Create/have a MEGA account in the system
   - Click "..." → "Update Password"
   - Enter new password
   - Should see success toast
   - Password should be updated in database

2. **Indexing:**
   - Configure date formats in Settings
   - Set local paths
   - Run "Index Local" on Files page
   - Should see folder sizes populate in Files tab
   - Uploads should work without "folder doesn't exist" error

---

## Commit & Push

```bash
cd ~/Development/TroubledMind/MegaManager
git add .
git commit -m "Add password update feature and document indexing requirements"
git push origin main
```
