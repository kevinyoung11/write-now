import { resolve } from 'path';
import { defineConfig } from 'vite';

export default defineConfig(({ command, mode }) => {
  if (command === 'serve') {
    // Development
    return {
      plugins: [
        // hmrPlugin({
        //   include: ['./src/**/*.ts'],
        //   presets: [presets.lit]
        // })
      ]
    };
  } else if (command === 'build') {
    switch (mode) {
      case 'production': {
        // Production: standard web page (default mode)
        return {
          build: {
            outDir: 'dist',
            rollupOptions: {
              input: {
                main: resolve(__dirname, 'index.html')
              }
            }
          },
          plugins: []
        };
      }

      case 'github': {
        // Production: github page (default mode)
        return {
          base: '/wordflow/',
          build: {
            outDir: 'dist',
            rollupOptions: {
              input: {
                main: resolve(__dirname, 'index.html')
              }
            }
          },
          plugins: []
        };
      }

      default: {
        console.error(`Error: unknown production mode ${mode}`);
        return null;
      }
    }
  }
});
