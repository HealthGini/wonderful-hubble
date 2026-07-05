
const fs = require('fs');
const code = fs.readFileSync('static/app.js', 'utf8');
try {
  new Function(code);
  console.log('🎉 static/app.js contains 100% VALID JavaScript syntax!');
} catch (err) {
  console.error('❌ SYNTAX ERROR FOUND:', err.message);
}
