// Centralized path config for writer scripts
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Root of the project (assume wrtr/ is always in the same place)
const projectRoot = path.join(__dirname, '../..');

export const BLOG_CONTENT_DIR = path.join(projectRoot, 'wrtr', 'blog');
export const BLOG_IMAGE_DIR = path.join(projectRoot, 'wrtr', 'blog-images');
export const GENERAL_IMAGE_DIR = path.join(projectRoot, 'wrtr', 'images');
export const PROMPTS_DIR = path.join(__dirname, 'system');

// Example usage:
// import { BLOG_CONTENT_DIR, BLOG_IMAGE_DIR, GENERAL_IMAGE_DIR, PROMPTS_DIR } from './paths.config'; 