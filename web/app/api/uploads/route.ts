import fs from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";
import { getWebRoot } from "@/lib/server/env";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_FILE_SIZE = 15 * 1024 * 1024;

export async function POST(request: Request) {
  const formData = await request.formData();
  const files = formData.getAll("files").filter((item): item is File => {
    return typeof item === "object" && item !== null && "arrayBuffer" in item;
  });

  if (!files.length) {
    return NextResponse.json({ files: [] });
  }

  const uploadRoot = path.join(getWebRoot(), ".uploads");
  await fs.mkdir(uploadRoot, { recursive: true });

  const saved = [];
  for (const file of files) {
    if (file.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { error: `${file.name} is larger than 15MB.` },
        { status: 400 }
      );
    }
    if (!isPdf(file)) {
      return NextResponse.json(
        { error: `${file.name} is not a PDF file.` },
        { status: 400 }
      );
    }
    const id = crypto.randomUUID();
    const safeName = sanitizeFileName(file.name);
    const directory = path.join(uploadRoot, id);
    const filePath = path.join(directory, safeName);
    await fs.mkdir(directory, { recursive: true });
    await fs.writeFile(filePath, Buffer.from(await file.arrayBuffer()));
    saved.push({
      id,
      name: safeName,
      size: file.size,
      path: filePath
    });
  }

  return NextResponse.json({ files: saved });
}

function isPdf(file: File) {
  return (
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  );
}

function sanitizeFileName(name: string) {
  const base = path.basename(name).replace(/[^\w.\-\u4e00-\u9fff]+/g, "-");
  return base.toLowerCase().endsWith(".pdf") ? base : `${base}.pdf`;
}
