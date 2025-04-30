# ✍️ Wrtr Blog Automation Suite

Welcome to the **Wrtr** tools! This suite automates blog post creation, AI-powered image generation, and hero image replacement for your Astro blog. Everything is modular, robust, and easy to use. 🚀

---

## 📦 What's Inside?

- **writeforme.ts** – Fully automates blog post creation (research, writing, metadata, hero image)
- **generateimages.ts** – Generate custom AI images for any description
- **replaceimage.ts** – Instantly replace the hero image of your latest blog post
- **setup/paths.config.ts** – Centralized config for all file and directory paths
- **setup/main.txt** – The main prompt template for AI calls (**edit this to change prompt style or instructions**)
- **setup/company.config.ts** – All company-specific info (name, features, competitors, etc. — **edit this to update company details**)
- **setup/system/** – All other prompt templates (advanced, rarely edited)

---

## 🚀 Standalone Usage (Local wrtr Folder)

You can use wrtr as a standalone tool! Just:

1. `cd wrtr`
2. Run `pnpm install` to install all dependencies (uses the included `package.json`)
3. Use the scripts:
   - `pnpm writeforme` – Run the blog automation script
   - `pnpm generateimages` – Generate custom images
   - `pnpm replaceimage` – Replace a blog hero image

You can still use the full project root commands if you prefer, but this makes it easy to work/test in isolation or CI.

---

## 🛠️ Setup & Prerequisites

1. **Install dependencies:**
   - From the project root: `pnpm install` (installs everything for the monorepo)
   - Or, from inside `wrtr/`: `pnpm install` (installs just the wrtr tool dependencies)

2. **Environment variables:**
   Create a `.env` file in the project root (or `wrtr/`):
   ```env
   OPENAI_API_KEY=sk-...
   PERPLEXITY_API_KEY=pxy-...
   ```
   Both are required for full automation. (You can skip Perplexity with a flag.)

3. **Check path config:**
   All output/input locations are set in [`setup/paths.config.ts`](./setup/paths.config.ts). If you move folders, update this file only!

---

## ✨ Usage

You can run scripts from the project root (with `pnpm exec tsx wrtr/...`) or from inside the `wrtr/` folder using the provided scripts:

```sh
# From inside wrtr/
pnpm writeforme "Your Blog Title" "A short description."
pnpm generateimages "A dreamy wedding venue at sunset"
pnpm replaceimage "A new description for the hero image"
```

### 1. 📝 Write a Blog Post Automatically

```sh
pnpm exec tsx wrtr/writeforme.ts "Your Blog Title" "A short description of your blog post."
```
- **Arguments:**
  1. Blog Title (optional)
  2. Blog Description (optional)
  3. Keywords (optional)
  4. `--skip-perplexity` (optional): Skip research step for faster draft

**Example:**
```sh
pnpm exec tsx wrtr/writeforme.ts "How to Automate Blogging with AI" "A step-by-step guide to AI-powered content creation."
```

- **What it does:**
  - Researches your topic (Perplexity, unless skipped)
  - Generates a markdown blog post (OpenAI)
  - Extracts metadata (title, description, image prompt)
  - Saves `.mdx` in `src/content/blog/`
  - Generates a hero image and saves as `.webp` in `public/blog/`

---

### 2. 🖼️ Generate Custom Images

```sh
pnpm exec tsx wrtr/generateimages.ts "A dreamy wedding venue at sunset" "A vintage camera on a table" "A bouquet of wildflowers"
```
- **Each argument is a separate image description**
- Images are saved as `.webp` in `public/images/`
- Prompts are styled using `setup/system/openai-image.txt`

---

### 3. 🔄 Replace the Hero Image of the Latest Blog Post

```sh
pnpm exec tsx wrtr/replaceimage.ts "A new description for the hero image" [path/to/image.webp]
```
- Finds the most recently modified `.mdx` in `src/content/blog/` (unless you specify an image path)
- Generates a new hero image using your description
- Overwrites the old image in `public/blog/` (or at the path you specify)

**Arguments:**
1. New image description (required)
2. Image path to replace (optional)
   - If omitted, replaces the hero image for the latest blog post (from frontmatter)
   - If provided, replaces the image at the given path (absolute or relative to project root)

**Examples:**
```sh
# Replace the latest blog post's hero image (default)
pnpm exec tsx wrtr/replaceimage.ts "A dreamy sunrise over a mountain lake"

# Replace a specific image anywhere in your project
pnpm exec tsx wrtr/replaceimage.ts "A cozy reading nook with plants" public/images/custom-hero.webp
```

- You'll see friendly progress and error messages in your terminal.
- The script only updates the image—it does not change the blog content or frontmatter.

**Tips:**
- Use a clear, vivid description for best results (e.g., "A dreamy clock melting into a soft sunrise, symbolizing time and new beginnings").
- If you see an error about missing frontmatter or image, check your latest blog post for the correct fields.
- The script only updates the image—it does not change the blog content or frontmatter.

---

## 🧩 How It Works

- **All file and directory paths** are managed in [`setup/paths.config.ts`](./setup/paths.config.ts). Update this file if you move folders!
- **Prompt templates:** Only edit [`setup/main.txt`](./setup/main.txt) to change the main prompt style or instructions for the AI.
- **Company info:** Only edit [`setup/company.config.ts`](./setup/company.config.ts) to update your company name, features, competitors, etc.
- **Advanced prompt templates** (for metadata, research, images) live in [`setup/system/`](./setup/system/) and rarely need editing.
- **No hardcoded paths** in scripts—everything is modular and maintainable.

---

## 🎨 System Prompts & Image Style

The `setup/system/` folder contains advanced prompt templates that control specific behaviors:

- **openai-image.txt** – Controls the style and instructions for all AI-generated images. **Edit this file to change the look, mood, or art direction of your generated images.**
- **perplexity.txt** – Controls how research is requested from Perplexity (for blog research).
- **openai-article.txt** – Controls the structure and instructions for the main blog article generation.
- **openai-metadata.txt** – Controls how metadata (title, description, image prompt) is extracted from the blog content.

**Most users only need to edit `setup/main.txt` and `setup/company.config.ts`.**

If you want to customize the style of your images, open `setup/system/openai-image.txt` and adjust the prompt text. For example, you can change the art style, color palette, or mood by editing the instructions in that file.

Advanced users can also tweak the other system prompts in `setup/system/` to fine-tune how research, metadata extraction, or article generation works.

---

## 🛡️ Troubleshooting

- **Missing API keys:** Make sure `.env` is present and correct.
- **File not found:** Check that your paths in `setup/paths.config.ts` match your project structure.
- **Image errors:** Ensure you have enough OpenAI credits and the prompt is valid.
- **Perplexity errors:** Use `--skip-perplexity` if you want to skip research or are out of quota.

---

## 🧙‍♂️ Advanced

- **Customizing prompts:** Only edit [`setup/main.txt`](./setup/main.txt) for the main prompt. Do not edit files in `setup/system/` unless you know what you're doing. To change image style, edit [`setup/system/openai-image.txt`](./setup/system/openai-image.txt).
- **Changing company info:** Only update [`setup/company.config.ts`](./setup/company.config.ts) for company-specific details.
- **Changing output locations:** Only update `setup/paths.config.ts`—all scripts will follow automatically.
- **Adding new scripts:** Import and use the path constants from `setup/paths.config.ts` for consistency.

---

## 💡 Example `.env`
```env
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pxy-...
```

---

## How to Run the Script

From the project root, run:

```sh
pnpm exec tsx wrtr/writeforme.ts 'Your Blog Title' 'A short description of your blog post.'
```

- The first argument is the blog post title.
- The second argument is a short description.
- Both are optional; if omitted, defaults will be used.

**Example:**
```sh
pnpm exec tsx wrtr/writeforme.ts 'How to Automate Blogging with AI' 'A step-by-step guide to AI-powered content creation.'
```

> **Tip:** If you ever see a `dquote>` or `quote>` prompt, it means your shell thinks a quote is unclosed. Using single quotes for arguments (as above) helps avoid this issue, especially if your title or description contains apostrophes or special characters.

---

## 🚦 Skipping Perplexity Research

You can now skip the Perplexity research step if you want a faster run or don't need external research/citations. Just add the `--skip-perplexity` flag:

```sh
pnpm exec tsx wrtr/writeforme.ts 'Your Blog Title' 'A short description' --skip-perplexity
```

- **What happens?** The script will NOT call the Perplexity API. It will generate the article using only OpenAI, with no external research summary or citations.
- **When to use:**
  - You want a quick draft and don't need research/citations.
  - You're hitting Perplexity API limits or want to save on usage.
  - You want to see OpenAI's "raw" take on your topic.
- **Output:** The rest of the workflow (metadata, MDX file, image) is unchanged and still follows all formatting/frontmatter rules.

---

## What Happens When You Run It?
1. **Research:**
   - Calls Perplexity API to get a research summary and citations for your topic.
2. **Article Generation:**
   - Uses OpenAI to generate a long-form markdown article based on the research.
3. **Metadata Extraction:**
   - Extracts title, description, and image prompt from the article.
4. **MDX File Creation:**
   - Saves the article as an `.mdx` file in `src/content/blog/` with proper frontmatter.
5. **Image Generation:**
   - Generates a webp illustration and saves it in `public/blog/`.

---

## Output
- **MDX file:** `src/content/blog/<slug>.mdx`
- **Image:** `public/blog/<slug>-<date>.webp`

---

## Troubleshooting
- Make sure your API keys are valid and have enough quota.
- If you see errors about missing dependencies, run `pnpm install` again.
- For debugging, check the console output for detailed logs and error messages.

---

## Notes
- This script is designed for use with an Astro + MDX blog setup.
- All code follows clean code and modularity best practices.
- If you want to customize prompts or output, check the `wrtr/setup/system/` directory.

---

## 🔄 Replacing a Blog's Hero Image

You can now update the hero image for the latest blog post with a single CLI command! This is perfect for refreshing visuals or fixing an image without editing the whole post.

**How to use:**
```sh
pnpm exec tsx wrtr/replaceimage.ts 'A new description for the hero image'
```
- The script finds the most recently modified blog post in `src/content/blog/`.
- It generates a new hero image using your description and the same style as the original blog automation.
- The new image is optimized and overwrites the old one in `public/blog/`.
- You'll see friendly progress and error messages in your terminal.

**Tips:**
- Use a clear, vivid description for best results (e.g., "A dreamy clock melting into a soft sunrise, symbolizing time and new beginnings").
- If you see an error about missing frontmatter or image, check your latest blog post for the correct fields.
- The script only updates the image—it does not change the blog content or frontmatter.

---

## 🖼️ Generating Custom Images with AI

You can now generate one or more custom images for your site using the new `generateimages` script! This is perfect for creating illustrations for blog posts, landing pages, or any creative need.

**How to use:**
```sh
pnpm exec tsx wrtr/generateimages.ts "A dreamy wedding venue at sunset" "A vintage camera on a table" "A bouquet of wildflowers"
```
- Each argument is a separate image description.
- The script will generate, optimize, and save a `.webp` image for each description.
- Images are saved to `/public/images/` with a slugified, timestamped filename for uniqueness.
- The prompt for image generation is loaded from `wrtr/setup/system/openai-image.txt` (edit this file to change the style for all images!).

**Tips:**
- Use clear, vivid descriptions for best results (e.g., "A couple dancing under string lights in a rustic barn").
- You can generate as many images as you want in a single command.
- All images are optimized for web and ready to use anywhere on your site.

---