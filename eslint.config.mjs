import jsxA11y from "eslint-plugin-jsx-a11y";
import security from "eslint-plugin-security";

export default [
  {
    ignores: [
      "node_modules/",
      "venv/",
      "data/",
      "*.parquet",
      "*.csv",
      ".pytest_cache/",
      "__pycache__/",
    ],
  },
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        process: "readonly",
        Buffer: "readonly",
        __dirname: "readonly",
        __filename: "readonly",
        module: "readonly",
        require: "readonly",
        exports: "readonly",
        setTimeout: "readonly",
        setInterval: "readonly",
        clearTimeout: "readonly",
        clearInterval: "readonly",
        fetch: "readonly",
        URL: "readonly",
      },
    },
    plugins: {
      "jsx-a11y": jsxA11y,
      security: security,
    },
    rules: {
      "security/detect-object-injection": "warn",
      "security/detect-eval-with-expression": "error",
      "security/detect-non-literal-regexp": "warn",
      "security/detect-non-literal-fs-filename": "warn",
      "security/detect-unsafe-regex": "warn",
      "security/detect-pseudoRandomBytes": "warn",
      "jsx-a11y/alt-text": "warn",
      "jsx-a11y/anchor-has-content": "warn",
      "jsx-a11y/aria-props": "warn",
      "jsx-a11y/aria-role": "warn",
      "jsx-a11y/heading-has-content": "warn",
      "jsx-a11y/html-has-lang": "warn",
      "jsx-a11y/img-redundant-alt": "warn",
      "jsx-a11y/no-access-key": "error",
      "jsx-a11y/tabindex-no-positive": "warn",
      "no-unused-vars": "warn",
      "no-undef": "warn",
    },
  },
];