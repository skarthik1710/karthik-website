# GitHub Setup Guide for karthik-website

## 🎯 Complete Setup Instructions

Follow these steps exactly to set up your GitHub repository.

---

## Step 1: Install Git (If Not Already Installed)

**Download:**
1. Go to https://git-scm.com/downloads
2. Download Git for Windows
3. Install with all default settings

**Verify Installation:**
```powershell
git --version
```
You should see something like: `git version 2.x.x`

---

## Step 2: Create GitHub Account & Repository

### A. Create Account (if you don't have one):
1. Go to https://github.com
2. Click "Sign up"
3. Follow the registration process
4. Verify your email

### B. Create Repository:
1. Log in to GitHub
2. Click the **"+"** icon (top right corner)
3. Select **"New repository"**
4. Fill in:
   - **Repository name**: `karthik-website`
   - **Description**: `Personal portfolio website - Digital Workplace & AI Consultant`
   - **Visibility**: ✅ **Public** (recommended) or Private
   - ✅ Check **"Add a README file"**
   - **Add .gitignore**: Choose "None" (we'll add our own)
   - **License**: Choose "None"
5. Click **"Create repository"**

### C. Copy Your Repository URL:
After creation, you'll see a URL like:
```
https://github.com/YOUR_USERNAME/karthik-website.git
```
**Copy this URL** - you'll need it in Step 4.

---

## Step 3: Configure Git (First Time Only)

Open PowerShell and run these commands:

```powershell
# Set your name (will appear in commits)
git config --global user.name "Karthikeyan Selvam"

# Set your email (use your GitHub email)
git config --global user.email "your-github-email@example.com"

# Verify configuration
git config --global --list
```

---

## Step 4: Initialize Git in Your Local Folder

```powershell
# Navigate to your website folder
cd C:\Users\KarthikaVanaraj\karthik-website

# Initialize Git repository
git init

# Check status
git status
```

You should see a list of "untracked files"

---

## Step 5: Add Files from This Guide

Before committing, copy these files to your `karthik-website` folder:

1. **README.md** (from outputs)
2. **.gitignore** (from outputs)

Copy them to: `C:\Users\KarthikaVanaraj\karthik-website\`

---

## Step 6: Stage and Commit Your Files

```powershell
# Add all files to staging
git add .

# Check what will be committed
git status

# Create your first commit
git commit -m "Initial commit: Portfolio website with Firebase hosting"
```

---

## Step 7: Connect to GitHub and Push

Replace `YOUR_USERNAME` with your actual GitHub username:

```powershell
# Add remote repository (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/karthik-website.git

# Verify remote was added
git remote -v

# Rename branch to main (GitHub standard)
git branch -M main

# Push to GitHub (first time)
git push -u origin main
```

**Note**: You may be prompted to log in to GitHub. Use your GitHub credentials.

---

## Step 8: Verify on GitHub

1. Go to your repository: `https://github.com/YOUR_USERNAME/karthik-website`
2. You should see all your files!
3. The README.md will display automatically on the repository page

---

## ✅ Setup Complete!

Your repository is now live on GitHub! 🎉

---

## 📝 Daily Workflow - Making Updates

### Every time you make changes to your website:

```powershell
# 1. Navigate to your folder
cd C:\Users\KarthikaVanaraj\karthik-website

# 2. Make your changes (edit HTML, add files, etc.)

# 3. Check what changed
git status

# 4. Add changes
git add .
# Or add specific files:
# git add public/index.html

# 5. Commit with descriptive message
git commit -m "Updated certifications section"

# 6. Push to GitHub
git push
```

---

## 🎨 Example: Updating Your Website

Let's say you updated the About section:

```powershell
cd C:\Users\KarthikaVanaraj\karthik-website

# Edit public/index.html (you already did this)

git status                                  # See what changed
git add public/index.html                   # Stage the file
git commit -m "Enhanced About section with work experience summary"
git push                                    # Push to GitHub

# Then deploy to Firebase:
firebase deploy --only hosting
```

---

## 🔧 Common Git Commands Reference

```powershell
# See current status
git status

# See commit history
git log
git log --oneline                # Compact view

# Add files
git add .                        # Add all changes
git add filename.html            # Add specific file
git add public/*                 # Add all files in folder

# Commit
git commit -m "Your message"

# Push to GitHub
git push

# Pull latest from GitHub
git pull

# See differences
git diff                         # See unstaged changes
git diff --staged               # See staged changes

# Undo changes (CAREFUL!)
git checkout -- filename.html   # Discard changes to file
git reset HEAD filename.html    # Unstage file
```

---

## 🌿 Working with Branches (Advanced)

For new features, create a branch:

```powershell
# Create and switch to new branch
git checkout -b add-chatbot-feature

# Make your changes...

# Commit changes
git add .
git commit -m "Added chatbot integration"

# Push branch to GitHub
git push -u origin add-chatbot-feature

# Switch back to main
git checkout main

# Merge branch (after testing)
git merge add-chatbot-feature
```

---

## 🚨 Troubleshooting

### Problem: "Permission denied" when pushing

**Solution**: GitHub authentication issue
```powershell
# Use Personal Access Token instead of password
# Go to: GitHub Settings → Developer settings → Personal access tokens
# Generate new token with 'repo' scope
# Use token as password when prompted
```

### Problem: "Failed to push"

**Solution**: Pull first, then push
```powershell
git pull origin main
git push
```

### Problem: "Merge conflict"

**Solution**: Resolve conflicts manually
```powershell
git status                      # See conflicted files
# Edit files to resolve conflicts
git add .
git commit -m "Resolved merge conflicts"
git push
```

---

## 📚 Git Workflow Diagram

```
Your Computer                    GitHub
─────────────                    ──────

Edit files
    │
    ▼
git add .
    │
    ▼
git commit -m "..."
    │
    ▼
git push ──────────────────────► Updates GitHub
                                      │
                                      ▼
                              Visible to everyone
```

---

## 🎯 Next Steps

After setup, you can:

1. **Clone on another computer**:
   ```powershell
   git clone https://github.com/YOUR_USERNAME/karthik-website.git
   ```

2. **Set up GitHub Actions** (automatic deployment)
3. **Add collaborators** (if working with others)
4. **Create project boards** (for planning)

---

## 📞 Need Help?

If you get stuck:
1. Check `git status` to see current state
2. Use `git log` to see commit history
3. Search error message on Google
4. GitHub documentation: https://docs.github.com

---

## ✅ Pre-Push Checklist

Before every push:
- [ ] Changes tested locally
- [ ] `firebase serve` works correctly
- [ ] Committed with clear message
- [ ] No sensitive data (passwords, API keys)
- [ ] README updated if needed

---

**You're all set! Happy coding! 🚀**
