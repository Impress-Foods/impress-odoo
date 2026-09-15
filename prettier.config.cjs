/** @type {import('prettier').Config} */

const config = {
  // https://github.com/prettier/prettier/issues/15388#issuecomment-1717746872
  plugins: [],
  bracketSpacing: false,
  printWidth: 88,
  proseWrap: "always",
  semi: true,
  trailingComma: "es5",
  xmlWhitespaceSensitivity: "preserve",
};

module.exports = config;
