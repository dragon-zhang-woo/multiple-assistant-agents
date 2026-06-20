/* eslint-disable @typescript-eslint/no-require-imports */

const fs = require("fs");

function normalizeReadlinkError(error, path) {
  if (!error || error.code !== "EISDIR") {
    return error;
  }

  const normalized = new Error(
    `EINVAL: invalid argument, readlink '${path}'`
  );
  normalized.errno = error.errno;
  normalized.code = "EINVAL";
  normalized.syscall = "readlink";
  normalized.path = error.path ?? path;
  return normalized;
}

const readlink = fs.readlink;
fs.readlink = function patchedReadlink(path, options, callback) {
  if (typeof options === "function") {
    callback = options;
    options = undefined;
  }

  return readlink.call(fs, path, options, (error, linkString) => {
    callback(normalizeReadlinkError(error, path), linkString);
  });
};

const readlinkSync = fs.readlinkSync;
fs.readlinkSync = function patchedReadlinkSync(path, options) {
  try {
    return readlinkSync.call(fs, path, options);
  } catch (error) {
    throw normalizeReadlinkError(error, path);
  }
};

if (fs.promises?.readlink) {
  const promisesReadlink = fs.promises.readlink;
  fs.promises.readlink = async function patchedPromisesReadlink(path, options) {
    try {
      return await promisesReadlink.call(fs.promises, path, options);
    } catch (error) {
      throw normalizeReadlinkError(error, path);
    }
  };
}
