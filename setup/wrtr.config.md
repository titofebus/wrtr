---
# =========================
# WRTR Project Configuration
# =========================
#
# Edit the values below to update your project/company/blog settings.
# All paths are relative to the project root.
#
# Comments (like these) explain what each field does!
#
company:
  type: CRM                # The type of company/product (e.g., CRM, SaaS, Agency)
  name: Gloam              # Your company or product name
  target: wedding professionals # Your main audience or customer type
  competitors:             # List of your main competitors
    - Dubsado
    - HoneyBook
  author: Tito             # Default author name for blog posts
  main_features:           # List your product's main features (for prompts, marketing, etc.)
    - advanced event & lead management
    - automations
    - branding
    - analytics
    - mobile access
    - robust API & webhooks
    - Glo AI is a proactive business partner that can automate emails, summarize conversations, join meetings virtually, and help you stay organized and ahead
blog:
  content_dir: wrtr/blog           # Where blog posts (.mdx) are saved
  image_dir: wrtr/blog-images      # Where hero images for blog posts are saved
  general_image_dir: wrtr/images   # Where general/generated images are saved
  prompts_dir: setup/system-prompts        # Where prompt templates are stored
  webp_quality: 80                # Compression quality (0-100, higher is better quality, default 80)
  webp_size: 1536x1024            # Size for webp images in WIDTHxHEIGHT format (default 1536x1024)
  default_frontmatter:             # Default frontmatter for new blog posts
    title: ""                      # Blog post title (leave blank for script to fill)
    description: ""                # Blog post description (leave blank for script to fill)
    pubDate: today                 # Publication date ("today" will be replaced automatically)
    image: ""                      # Path to hero image (script will fill)
    author: Tito                   # Author name (usually matches company.author)
---

# WRTR Project Configuration 🎉

Welcome! This is your one-stop config file for the WRTR project. Edit the values above to update your project/company/blog settings.

- All paths are relative to the project root.
- You can add more features or competitors as needed.
- The `pubDate` field will be set to today's date automatically by the scripts.

If you have any questions, ask Tito or check the docs! 🚀
