import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const projectRoot = path.resolve(__dirname, '../..');
const configPath = path.join(__dirname, '../wrtr.config.md');

const file = fs.readFileSync(configPath, 'utf8');
const { data: config } = matter(file);

// Company config
export const COMPANY_TYPE = config.company.type;
export const COMPANY_NAME = config.company.name;
export const COMPANY_TARGET = config.company.target;
export const COMPANY_COMPETITORS = config.company.competitors;
export const COMPANY_AUTHOR = config.company.author;
export const COMPANY_MAIN_FEATURES = config.company.main_features;

// Blog/path config
export const BLOG_CONTENT_DIR = path.join(projectRoot, config.blog.content_dir);
export const BLOG_IMAGE_DIR = path.join(projectRoot, config.blog.image_dir);
export const GENERAL_IMAGE_DIR = path.join(projectRoot, config.blog.general_image_dir);
export const PROMPTS_DIR = path.join(projectRoot, config.blog.prompts_dir);

// Blog frontmatter
type BlogFrontmatter = {
  title: string;
  description: string;
  pubDate: string;
  image: string;
  author: string;
};

export const defaultBlogFrontmatter: BlogFrontmatter = {
  ...config.blog.default_frontmatter,
  pubDate: new Date().toISOString().split('T')[0], // Always today's date
  author: config.company.author,
};

export type { BlogFrontmatter }; 