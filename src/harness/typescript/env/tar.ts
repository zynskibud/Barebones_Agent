// Tar archives for the cloud env.
//
// Node has no tar module, and the harness takes no npm package for it, so
// this file writes and reads the archives by hand. The Python harness uses
// its standard tarfile module for the same two jobs:
//
// - packFolder: the upload. A gzip tar of one folder with the members "./",
//   "./a.py", "./tests/", and so on, like tarfile.add(root, arcname=".").
// - extractSafely: the download. It extracts into a folder with the rules of
//   the tarfile "data" filter, and it skips a member that the filter rejects,
//   with a note on stderr.
//
// The format is ustar. A name or link longer than 100 bytes goes in a pax
// header. The reader also reads the GNU long name records that GNU tar in
// the sandbox writes.

import fs from "node:fs";
import nodePath from "node:path";
import zlib from "node:zlib";

import { posixJoin, posixSplit } from "./base.ts";
import { byCodePoint, isInside, realPath } from "./local.ts";

const BLOCK = 512;
const NAME_BYTES = 100;

// One archive member: a file ("0"), hard link ("1"), symlink ("2"), folder ("5"), or other type.
export type Member = {
  name: string;
  type: string;
  mode: number;
  mtime: number;
  linkname: string;
  data: Buffer;
};

type Header = {
  name: string;
  type: string;
  mode: number;
  uid: number;
  gid: number;
  size: number;
  mtime: number;
  linkname: string;
};

// Return a gzip tar of every file, folder, and symlink under root.
export function packFolder(root: string): Buffer {
  const blocks: Buffer[] = [];
  addEntry(blocks, root, ".");
  blocks.push(Buffer.alloc(BLOCK * 2));
  return zlib.gzipSync(Buffer.concat(blocks));
}

// Add one path, and for a folder every path below it in sorted order.
// Symlinks are stored as symlinks, not followed.
function addEntry(blocks: Buffer[], path: string, name: string): void {
  const stat = fs.lstatSync(path);
  const base = {
    mode: stat.mode & 0o7777,
    uid: stat.uid,
    gid: stat.gid,
    mtime: Math.floor(stat.mtimeMs / 1000),
  };
  if (stat.isSymbolicLink()) {
    pushHeader(blocks, { ...base, name, type: "2", size: 0, linkname: fs.readlinkSync(path) });
  } else if (stat.isDirectory()) {
    pushHeader(blocks, { ...base, name: name + "/", type: "5", size: 0, linkname: "" });
    for (const child of fs.readdirSync(path).sort(byCodePoint)) {
      addEntry(blocks, nodePath.join(path, child), posixJoin(name, child));
    }
  } else if (stat.isFile()) {
    const data = fs.readFileSync(path);
    pushHeader(blocks, { ...base, name, type: "0", size: data.length, linkname: "" });
    blocks.push(data, Buffer.alloc(padding(data.length)));
  } else {
    fs.writeSync(2, `cloud env: skipped ${name} in the upload: it is not a file, folder, or symlink\n`);
  }
}

// Add the header of one member, with a pax header first when a name is too long.
function pushHeader(blocks: Buffer[], header: Header): void {
  let records = "";
  if (Buffer.byteLength(header.name) > NAME_BYTES) records += paxRecord("path", header.name);
  if (Buffer.byteLength(header.linkname) > NAME_BYTES) records += paxRecord("linkpath", header.linkname);
  if (records !== "") {
    const data = Buffer.from(records, "utf8");
    const pax = { name: "././@PaxHeader", type: "x", mode: 0o644, uid: 0, gid: 0, size: data.length, mtime: header.mtime, linkname: "" };
    blocks.push(headerBlock(pax), data, Buffer.alloc(padding(data.length)));
  }
  blocks.push(headerBlock(header));
}

// One pax record: "<length> <key>=<value>\n", where length counts the whole record.
function paxRecord(key: string, value: string): string {
  const body = ` ${key}=${value}\n`;
  const size = Buffer.byteLength(body);
  let length = size + String(size).length;
  if (String(length).length > String(size).length) length = size + String(length).length;
  return `${length}${body}`;
}

function headerBlock(header: Header): Buffer {
  const block = Buffer.alloc(BLOCK);
  writeText(block, 0, NAME_BYTES, header.name);
  writeOctal(block, 100, 8, header.mode);
  writeOctal(block, 108, 8, header.uid);
  writeOctal(block, 116, 8, header.gid);
  writeOctal(block, 124, 12, header.size);
  writeOctal(block, 136, 12, header.mtime);
  // The checksum counts its own field as spaces.
  block.fill(0x20, 148, 156);
  block.write(header.type, 156, 1, "latin1");
  writeText(block, 157, NAME_BYTES, header.linkname);
  block.write("ustar\0", 257, 6, "latin1");
  block.write("00", 263, 2, "latin1");
  let sum = 0;
  for (const byte of block) sum += byte;
  writeOctal(block, 148, 7, sum);
  return block;
}

function writeText(block: Buffer, offset: number, length: number, value: string): void {
  Buffer.from(value, "utf8").copy(block, offset, 0, length);
}

// Octal digits, zero padded, then one NUL.
function writeOctal(block: Buffer, offset: number, length: number, value: number): void {
  const digits = value.toString(8).padStart(length - 1, "0");
  if (digits.length > length - 1) throw new Error(`the value ${value} does not fit in a tar header`);
  block.write(digits + "\0", offset, length, "latin1");
}

function padding(size: number): number {
  return (BLOCK - (size % BLOCK)) % BLOCK;
}

// Read every member of a gzip tar archive.
export function readArchive(gzipped: Buffer): Member[] {
  const data = zlib.gunzipSync(gzipped);
  const members: Member[] = [];
  let longName: string | null = null;
  let longLink: string | null = null;
  let pax = new Map<string, string>();
  let offset = 0;
  while (offset + BLOCK <= data.length) {
    const block = data.subarray(offset, offset + BLOCK);
    if (block.every((byte) => byte === 0)) break;
    checkSum(block);
    const type = block[156] === 0 ? "0" : String.fromCharCode(block[156]);
    const meta = type === "L" || type === "K" || type === "x" || type === "g";
    let size = readNumber(block, 124, 12);
    if (!meta && pax.has("size")) size = Number(pax.get("size"));
    const body = data.subarray(offset + BLOCK, offset + BLOCK + size);
    offset += BLOCK + size + padding(size);
    if (type === "L") longName = cText(body);
    else if (type === "K") longLink = cText(body);
    else if (type === "x") pax = readPax(body);
    if (meta) continue;
    members.push({
      name: longName ?? pax.get("path") ?? headerName(block),
      type,
      mode: readNumber(block, 100, 8),
      mtime: pax.has("mtime") ? Math.floor(Number(pax.get("mtime"))) : readNumber(block, 136, 12),
      linkname: longLink ?? pax.get("linkpath") ?? cText(block.subarray(157, 157 + NAME_BYTES)),
      data: Buffer.from(body),
    });
    longName = null;
    longLink = null;
    pax = new Map();
  }
  return members;
}

// The name field, with the ustar prefix field in front when there is one.
// GNU tar uses the prefix bytes for other data, so only a POSIX header has a prefix.
function headerName(block: Buffer): string {
  const name = cText(block.subarray(0, NAME_BYTES));
  if (block.toString("latin1", 257, 263) !== "ustar\0") return name;
  const prefix = cText(block.subarray(345, 500));
  return prefix === "" ? name : prefix + "/" + name;
}

// Text up to the first NUL.
function cText(bytes: Buffer): string {
  const end = bytes.indexOf(0);
  return bytes.toString("utf8", 0, end === -1 ? bytes.length : end);
}

// An octal field, or a base-256 field when the high bit of the first byte is set.
function readNumber(block: Buffer, offset: number, length: number): number {
  if (block[offset] & 0x80) {
    let value = block[offset] & 0x7f;
    for (let index = 1; index < length; index++) value = value * 256 + block[offset + index];
    return value;
  }
  const digits = block.toString("latin1", offset, offset + length).replace(/[\0 ]+/g, "");
  return digits === "" ? 0 : parseInt(digits, 8);
}

function checkSum(block: Buffer): void {
  let sum = 0;
  for (let index = 0; index < BLOCK; index++) sum += index >= 148 && index < 156 ? 0x20 : block[index];
  if (sum !== readNumber(block, 148, 8)) throw new Error("the download archive has a bad tar header");
}

// The records of one pax header.
function readPax(body: Buffer): Map<string, string> {
  const records = new Map<string, string>();
  let position = 0;
  while (position < body.length) {
    const space = body.indexOf(0x20, position);
    if (space === -1) break;
    const length = parseInt(body.toString("latin1", position, space), 10);
    if (!(length > 0)) break;
    const record = body.toString("utf8", space + 1, position + length - 1);
    const equals = record.indexOf("=");
    if (equals > 0) records.set(record.slice(0, equals), record.slice(equals + 1));
    position += length;
  }
  return records;
}

// Extract the members into dest with the rules of Python's tarfile "data" filter.
// A member that the filter rejects is skipped, with a note on stderr.
export function extractSafely(members: Member[], dest: string): void {
  const root = realPath(dest);
  const folders: Array<{ path: string; mtime: number }> = [];
  for (const member of members) {
    const name = member.name.replace(/^\/+/, "");
    const problem = filterProblem(member, name, root);
    if (problem !== null) {
      fs.writeSync(2, `cloud env: skipped ${member.name} in the download: ${problem}\n`);
      continue;
    }
    const target = nodePath.join(dest, name);
    const parent = nodePath.dirname(target);
    if (!fs.existsSync(parent)) fs.mkdirSync(parent, { recursive: true });
    if (member.type === "5") {
      if (!fs.existsSync(target)) fs.mkdirSync(target);
      folders.push({ path: target, mtime: member.mtime });
    } else if (member.type === "2") {
      if (lexists(target)) fs.unlinkSync(target);
      fs.symlinkSync(member.linkname, target);
    } else if (member.type === "1") {
      if (lexists(target)) fs.unlinkSync(target);
      fs.linkSync(nodePath.join(dest, member.linkname), target);
      setTimes(target, member.mtime);
    } else {
      fs.writeFileSync(target, member.data);
      fs.chmodSync(target, fileMode(member.mode));
      setTimes(target, member.mtime);
    }
  }
  // Folder times last, deepest first, because extracting a child changes them.
  folders.sort((a, b) => byCodePoint(b.path, a.path));
  for (const folder of folders) setTimes(folder.path, folder.mtime);
}

// Return why the data filter rejects a member, or null when it may be extracted.
function filterProblem(member: Member, name: string, root: string): string | null {
  const known = ["0", "7", "1", "2", "5"];
  const place = realPath(posixJoin(root, name));
  if (!isInside(place, root)) return `'${name}' would be extracted to '${place}', which is outside the destination`;
  if (!known.includes(member.type)) return `'${name}' is a special file`;
  if (member.type !== "1" && member.type !== "2") return null;
  if (member.linkname.startsWith("/")) return `'${name}' is a link to an absolute path`;
  const from = member.type === "2" ? posixJoin(root, posixSplit(name)[0]) : root;
  const linked = realPath(posixJoin(from, member.linkname));
  if (!isInside(linked, root)) return `'${name}' would link to '${linked}', which is outside the destination`;
  return null;
}

// The data filter mode of a file: no high bits, no group or other write,
// no execute bits unless the owner may execute, and owner read and write.
function fileMode(mode: number): number {
  let result = mode & 0o755;
  if (!(result & 0o100)) result &= ~0o111;
  return result | 0o600;
}

function setTimes(path: string, mtime: number): void {
  fs.utimesSync(path, mtime, mtime);
}

function lexists(path: string): boolean {
  try {
    fs.lstatSync(path);
    return true;
  } catch {
    return false;
  }
}
