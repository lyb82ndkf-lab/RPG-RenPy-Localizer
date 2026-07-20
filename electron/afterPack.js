const fs = require('fs');
const path = require('path');

function touchRecursive(target, timestamp) {
  if (!fs.existsSync(target)) return;
  const stat = fs.lstatSync(target);
  if (stat.isDirectory()) {
    for (const name of fs.readdirSync(target)) {
      touchRecursive(path.join(target, name), timestamp);
    }
  }
  try {
    fs.utimesSync(target, timestamp, timestamp);
  } catch (error) {
    // Some generated files may be locked briefly by signing tools. Ignore; final exe timestamps remain normal.
  }
}

exports.default = async function afterPack(context) {
  const timestamp = new Date();
  touchRecursive(context.appOutDir, timestamp);
};
