# Wordflow Frontend

This frontend serves the vendored Wordflow app directly at `/`.

The root `index.html` loads:

- `/wordflow/global.css`
- `/wordflow/assets/main-*.js`
- `<wordflow-wordflow>`

There is no app shell, router, or iframe wrapper in this package.
