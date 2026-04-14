import { SupportedLanguages } from './languages.js';

const RUBY_EXTENSIONLESS_FILES = new Set([
  'Rakefile', 'Gemfile', 'Guardfile', 'Vagrantfile', 'Brewfile',
]);

const EXTENSION_MAP: Record<SupportedLanguages, readonly string[]> = {
  [SupportedLanguages.JavaScript]: ['.js', '.jsx', '.mjs', '.cjs'],
  [SupportedLanguages.TypeScript]: ['.ts', '.tsx', '.mts', '.cts'],
  [SupportedLanguages.Python]: ['.py'],
  [SupportedLanguages.Java]: ['.java'],
  [SupportedLanguages.C]: ['.c'],
  [SupportedLanguages.CPlusPlus]: ['.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.hh'],
  [SupportedLanguages.CSharp]: ['.cs'],
  [SupportedLanguages.Go]: ['.go'],
  [SupportedLanguages.Ruby]: ['.rb', '.rake', '.gemspec'],
  [SupportedLanguages.Rust]: ['.rs'],
  [SupportedLanguages.PHP]: ['.php', '.phtml', '.php3', '.php4', '.php5', '.php8'],
  [SupportedLanguages.Kotlin]: ['.kt', '.kts'],
  [SupportedLanguages.Swift]: ['.swift'],
  [SupportedLanguages.Dart]: ['.dart'],
  [SupportedLanguages.Vue]: ['.vue'],
  [SupportedLanguages.Cobol]: ['.cbl', '.cob', '.cpy', '.cobol'],
} satisfies Record<SupportedLanguages, readonly string[]>;

const extToLang = new Map<string, SupportedLanguages>();
for (const [lang, exts] of Object.entries(EXTENSION_MAP) as [SupportedLanguages, readonly string[]][]) {
  for (const ext of exts) extToLang.set(ext, lang);
}

export const getLanguageFromFilename = (filename: string): SupportedLanguages | null => {
  const lastDot = filename.lastIndexOf('.');
  if (lastDot >= 0) {
    const ext = filename.slice(lastDot).toLowerCase();
    const lang = extToLang.get(ext);
    if (lang !== undefined) return lang;
  }
  const basename = filename.split('/').pop() || filename;
  if (RUBY_EXTENSIONLESS_FILES.has(basename)) return SupportedLanguages.Ruby;
  return null;
};

const SYNTAX_MAP: Record<SupportedLanguages, string> = {
  [SupportedLanguages.JavaScript]: 'javascript',
  [SupportedLanguages.TypeScript]: 'typescript',
  [SupportedLanguages.Python]: 'python',
  [SupportedLanguages.Java]: 'java',
  [SupportedLanguages.C]: 'c',
  [SupportedLanguages.CPlusPlus]: 'cpp',
  [SupportedLanguages.CSharp]: 'csharp',
  [SupportedLanguages.Go]: 'go',
  [SupportedLanguages.Ruby]: 'ruby',
  [SupportedLanguages.Rust]: 'rust',
  [SupportedLanguages.PHP]: 'php',
  [SupportedLanguages.Kotlin]: 'kotlin',
  [SupportedLanguages.Swift]: 'swift',
  [SupportedLanguages.Dart]: 'dart',
  [SupportedLanguages.Vue]: 'typescript',
  [SupportedLanguages.Cobol]: 'cobol',
} satisfies Record<SupportedLanguages, string>;

const AUXILIARY_SYNTAX_MAP: Record<string, string> = {
  json: 'json', yaml: 'yaml', yml: 'yaml', md: 'markdown', mdx: 'markdown',
  html: 'markup', htm: 'markup', erb: 'markup', xml: 'markup',
  css: 'css', scss: 'css', sass: 'css', sh: 'bash', bash: 'bash', zsh: 'bash',
  sql: 'sql', toml: 'toml', ini: 'ini', dockerfile: 'docker',
};

const AUXILIARY_BASENAME_MAP: Record<string, string> = {
  Makefile: 'makefile', Dockerfile: 'docker',
};

export const getSyntaxLanguageFromFilename = (filePath: string): string => {
  const lang = getLanguageFromFilename(filePath);
  if (lang) return SYNTAX_MAP[lang];
  const ext = filePath.split('.').pop()?.toLowerCase();
  if (ext && ext in AUXILIARY_SYNTAX_MAP) return AUXILIARY_SYNTAX_MAP[ext];
  const basename = filePath.split('/').pop() || '';
  if (basename in AUXILIARY_BASENAME_MAP) return AUXILIARY_BASENAME_MAP[basename];
  return 'text';
};
