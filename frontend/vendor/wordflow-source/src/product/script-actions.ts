import type { PromptDataLocal } from '../types/wordflow';

const created = new Date(0).toISOString();
const recommendedModels = ['gpt-5.4', 'gpt-5.4-mini'];

function scriptActionPrompt(
  key: string,
  title: string,
  prompt: string,
  tag: string,
  description: string,
  icon: string,
  temperature: number
): PromptDataLocal {
  return {
    key,
    title,
    prompt,
    tags: ['script', tag],
    temperature,
    userID: '',
    userName: 'Write Now',
    description,
    icon,
    forkFrom: '',
    promptRunCount: 0,
    created,
    outputParsingPattern: '(.*)',
    outputParsingReplacement: '$1',
    recommendedModels,
    injectionMode: 'replace'
  };
}

export const SCRIPT_ACTION_PROMPTS: PromptDataLocal[] = [
  scriptActionPrompt(
    'script-action-expand',
    '扩写',
    '你是视频脚本编辑。请扩写以下内容，保留原观点，增加具体细节和口播节奏：{{text}}',
    'expand',
    '扩写选区或当前段落',
    '+',
    0.4
  ),
  scriptActionPrompt(
    'script-action-rewrite',
    '改写',
    '你是视频脚本编辑。请改写以下内容，让表达更清楚、更自然，不改变核心意思：{{text}}',
    'rewrite',
    '改写选区或当前段落',
    'edit',
    0.3
  ),
  scriptActionPrompt(
    'script-action-oralize',
    '口播化',
    '你是视频口播脚本编辑。请把以下内容改成更适合真人口播的表达，句子更短，节奏更顺：{{text}}',
    'oralize',
    '转换为口播表达',
    'play',
    0.35
  ),
  scriptActionPrompt(
    'script-action-shorten',
    '压缩',
    '你是视频脚本编辑。请压缩以下内容，保留核心信息，删掉重复和松散表达：{{text}}',
    'shorten',
    '压缩选区或当前段落',
    '-',
    0.2
  )
];

