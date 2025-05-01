import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const projectRoot = path.resolve(__dirname, '../../..');

// Try both possible config locations
const configPaths = [
  path.join(__dirname, '../wrtr.config.md'),
  path.join(__dirname, '../../wrtr.config.md'),
];

let configPath = configPaths.find(p => fs.existsSync(p));
if (!configPath) {
  throw new Error(`Could not find wrtr.config.md in any known location: ${configPaths.join(', ')}`);
}

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
const promptDirCandidates = [
  path.join(projectRoot, config.blog.prompts_dir),
  path.join(__dirname, '../', config.blog.prompts_dir),
  path.join(__dirname, '../../', config.blog.prompts_dir),
];
const PROMPTS_DIR: string = (() => {
  const found = promptDirCandidates.find(p => fs.existsSync(p));
  if (!found) throw new Error(`Could not find prompts_dir in any known location: ${promptDirCandidates.join(', ')}`);
  return found;
})();
export { PROMPTS_DIR };
export const BLOG_CONTENT_DIR = path.join(projectRoot, config.blog.content_dir);
export const BLOG_IMAGE_DIR = path.join(projectRoot, config.blog.image_dir);
export const GENERAL_IMAGE_DIR = path.join(projectRoot, config.blog.general_image_dir);
export const WEBP_QUALITY = typeof config.blog.webp_quality === 'number' ? config.blog.webp_quality : 80;
export const WEBP_SIZE = typeof config.blog.webp_size === 'string' ? config.blog.webp_size : '1536x1024';
const [WEBP_WIDTH, WEBP_HEIGHT] = WEBP_SIZE.split('x').map(Number);
export { WEBP_WIDTH, WEBP_HEIGHT };

// Blog frontmatter
type BlogFrontmatter = {
  title: string;
  description: string;
  pubDate: string;
  image: string;
  author: string;
};

export const DEFAULT_BLOG_FRONTMATTER: BlogFrontmatter = {
  ...config.blog.default_frontmatter,
  pubDate: new Date().toISOString().split('T')[0], // Always today's date
  author: config.company.author,
};

export type { BlogFrontmatter }; 