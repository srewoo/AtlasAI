const esbuild = require('esbuild');
const { copy } = require('esbuild-plugin-copy');
const fs = require('fs');
const path = require('path');

const isDev = process.argv.includes('--watch');
const isProd = process.env.NODE_ENV === 'production';

// Auto-increment version on production builds
function updateVersion() {
  const manifestPath = path.join(__dirname, 'src/manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const [major, minor, patch] = manifest.version.split('.').map(Number);
  manifest.version = `${major}.${minor}.${patch + 1}`;
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log(`Version updated to ${manifest.version}`);
}

if (isProd) {
  updateVersion();
}

// Common build options
const buildOptions = {
  bundle: true,
  sourcemap: isDev ? 'inline' : false,
  minify: isProd,
  target: 'chrome88',
  define: {
    'process.env.NODE_ENV': isProd ? '"production"' : '"development"'
  }
};

// Copy plugin configuration
const copyPlugin = copy({
  resolveFrom: 'cwd',
  assets: [
    {
      from: 'src/html/*.html',
      to: 'dist/'
    },
    {
      from: 'src/icons/**/*',
      to: 'dist/icons/'
    },
    {
      from: 'src/manifest.json',
      to: 'dist/manifest.json'
    }
  ]
});

// Build configurations for each entry point
const configs = [
  {
    ...buildOptions,
    entryPoints: ['src/js/popup/popup.js'],
    outfile: 'dist/popup.js',
    format: 'iife',
    plugins: [copyPlugin]
  },
  {
    ...buildOptions,
    entryPoints: ['src/js/settings/settings.js'],
    outfile: 'dist/settings.js',
    format: 'iife'
  },
  {
    ...buildOptions,
    entryPoints: ['src/js/background/background.js'],
    outfile: 'dist/background.js',
    format: 'iife'
  },
  {
    ...buildOptions,
    entryPoints: ['src/js/settings/wizard.js'],
    outfile: 'dist/wizard.js',
    format: 'iife'
  },
  {
    ...buildOptions,
    entryPoints: ['src/js/content/contextMenu.js'],
    outfile: 'dist/content.js',
    format: 'iife'
  },
  {
    ...buildOptions,
    entryPoints: ['src/styles/base.css'],
    outfile: 'dist/styles.css',
    loader: { '.css': 'css' },
    bundle: true
  }
];

// Build function
async function build() {
  try {
    // Clean dist folder
    if (fs.existsSync('dist')) {
      fs.rmSync('dist', { recursive: true });
    }
    fs.mkdirSync('dist', { recursive: true });

    console.log(isDev ? 'Building in development mode...' : 'Building for production...');

    // Build all configs
    const buildPromises = configs.map(config => esbuild.build(config));
    await Promise.all(buildPromises);

    console.log('Build complete!');

    if (isDev) {
      console.log('Watching for changes...');
    }
  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1);
  }
}

// Run build
if (isDev) {
  // Watch mode
  configs.forEach(config => {
    esbuild.context(config).then(ctx => ctx.watch());
  });
} else {
  build();
}
