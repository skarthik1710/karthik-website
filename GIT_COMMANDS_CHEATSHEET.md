# Git Command Quick Reference for karthik-website

## 🚀 Quick Start Commands

```powershell
# First time setup (run once)
cd C:\Users\KarthikaVanaraj\karthik-website
git init
git config --global user.name "Karthikeyan Selvam"
git config --global user.email "your-email@example.com"
git remote add origin https://github.com/YOUR_USERNAME/karthik-website.git
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main
```

---

## 📝 Daily Workflow (Use These Most Often)

```powershell
# Standard update workflow
cd C:\Users\KarthikaVanaraj\karthik-website

# 1. See what changed
git status

# 2. Add your changes
git add .

# 3. Save with message
git commit -m "Description of what you changed"

# 4. Upload to GitHub
git push
```

---

## 🔍 Check Status

```powershell
git status              # What files changed?
git log                 # History of commits
git log --oneline       # Compact history
git diff                # See exact changes
```

---

## ➕ Adding Files

```powershell
git add .                       # Add everything
git add public/index.html       # Add one file
git add public/*.html           # Add all HTML files
git add *.jpg                   # Add all JPG files
```

---

## 💾 Committing

```powershell
git commit -m "Short description"
git commit -m "Updated hero section with new CTA buttons"
git commit -m "Fixed mobile responsive layout"
git commit -m "Added certification verification links"
```

---

## ⬆️ Pushing to GitHub

```powershell
git push                        # Standard push
git push origin main            # Push to main branch
git push -u origin main         # First time push (with tracking)
```

---

## ⬇️ Pulling from GitHub

```powershell
git pull                        # Get latest changes
git pull origin main            # Pull from main branch
```

---

## 🌿 Branch Commands

```powershell
git branch                      # List branches
git branch new-feature          # Create branch
git checkout new-feature        # Switch to branch
git checkout -b new-feature     # Create and switch
git checkout main               # Back to main
git merge new-feature           # Merge branch into current
```

---

## ↩️ Undo Commands (Be Careful!)

```powershell
# Undo unstaged changes to a file
git checkout -- filename.html

# Unstage a file (keep changes)
git reset HEAD filename.html

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes) ⚠️ DANGEROUS
git reset --hard HEAD~1
```

---

## 🔧 Configuration

```powershell
# View config
git config --list
git config --global --list

# Set name and email
git config --global user.name "Your Name"
git config --global user.email "your@email.com"

# View remote URL
git remote -v

# Change remote URL
git remote set-url origin NEW_URL
```

---

## 📋 Complete Update Example

```powershell
# Scenario: You updated the about section

cd C:\Users\KarthikaVanaraj\karthik-website

# Check status
git status

# Add the changes
git add public/index.html

# Commit with message
git commit -m "Updated About section with 18+ years experience"

# Push to GitHub
git push

# Deploy to Firebase
firebase deploy --only hosting
```

---

## 🎯 Common Workflows

### Workflow 1: Quick Update
```powershell
git add .
git commit -m "Quick fix"
git push
```

### Workflow 2: Careful Update
```powershell
git status                              # See what changed
git diff                                # Review changes
git add public/index.html               # Add specific files
git status                              # Verify staging
git commit -m "Descriptive message"
git push
```

### Workflow 3: Multiple Files
```powershell
git add public/index.html
git add public/experience.html
git add public/Profile.jpg
git commit -m "Updated homepage and experience page with new profile photo"
git push
```

---

## 🚨 Emergency Commands

### Mistake in last commit message?
```powershell
git commit --amend -m "Corrected message"
git push --force
```

### Forgot to add a file to last commit?
```powershell
git add forgotten-file.html
git commit --amend --no-edit
git push --force
```

### Want to see what you're about to commit?
```powershell
git diff --staged
```

---

## 📞 Help Commands

```powershell
git help                # General help
git help add            # Help for specific command
git help commit
git help push
```

---

## ✅ Pre-Commit Checklist

Before `git commit`:
- [ ] Tested changes locally
- [ ] No sensitive data (passwords, keys)
- [ ] Descriptive commit message ready
- [ ] Only committing intended files

---

## 💡 Pro Tips

1. **Commit often** - Small, frequent commits are better
2. **Descriptive messages** - Future you will thank you
3. **Review before commit** - Use `git diff`
4. **Pull before push** - Avoid conflicts
5. **Never commit secrets** - Check .gitignore

---

## 📊 Git Status Explained

```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  modified:   public/index.html        ← File changed but not added

Untracked files:
  public/new-page.html                 ← New file not added

nothing added to commit
```

---

**Keep this handy for quick reference! 📌**
