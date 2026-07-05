
const fs = require('fs');
const code = fs.readFileSync('static/app.js', 'utf8');

global.window = global;
global.document = {
  getElementById: (id) => ({
    classList: { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false },
    addEventListener: () => {},
    setAttribute: () => {},
    getAttribute: () => null,
    innerHTML: '',
    value: '',
    src: ''
  }),
  addEventListener: (event, cb) => {
    if (event === 'DOMContentLoaded') setTimeout(cb, 10);
  },
  querySelectorAll: () => []
};
global.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {}
};
global.location = { hash: '#/', href: '' };
global.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) });

try {
  eval(code);
  console.log('✅ app.js evaluated without throwing syntax or top-level runtime errors!');
} catch (err) {
  console.error('❌ Error executing app.js:', err);
}
