"use server";

import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";
import type { OfficialPostIn } from "@/lib/officialPosts";
import type { Scorecard } from "./kinerja";

type Result<T> = { ok: true; result: T } | { ok: false; error: string };

export interface PostsResult {
  received: number;
  stored: number;
  updated: number;
  duplicates_dropped: number;
}

export interface ScoreInput {
  indicator: string;
  score: number | null;
  unavailable_reason: string | null;
  evidence: string;
}

/** Unggah satu potong unggahan akun resmi. Mengunggah ulang memperbarui angkanya. */
export async function uploadOfficialPosts(
  projectId: string,
  items: OfficialPostIn[],
): Promise<Result<PostsResult>> {
  try {
    const result = await api<PostsResult>(`/projects/${projectId}/comm-performance/posts`, {
      method: "POST",
      body: JSON.stringify({ items }),
    });
    revalidatePath("/kinerja");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

/** Simpan isian indikator satu lembaga untuk satu bulan. */
export async function saveScores(
  projectId: string,
  subject: string,
  period: string,
  items: ScoreInput[],
): Promise<Result<Scorecard>> {
  try {
    const result = await api<Scorecard>(`/projects/${projectId}/comm-performance/scores`, {
      method: "PUT",
      body: JSON.stringify({ subject, period, items }),
    });
    revalidatePath("/kinerja");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}

export interface YouTubeFetchResult {
  channel_id: string;
  channel_title: string;
  account: string;
  subscribers: number | null;
  n_videos: number;
  since_days: number;
  truncated: boolean;
  quota_units: number;
  result: PostsResult;
  limitations: string[];
}

/** Ambil video kanal YouTube RESMI lembaga lewat YouTube Data API, lalu simpan. */
export async function fetchYouTubeChannel(
  projectId: string,
  channel: string,
  sinceDays: number,
  maxVideos: number,
): Promise<Result<YouTubeFetchResult>> {
  try {
    const result = await api<YouTubeFetchResult>(`/projects/${projectId}/comm-performance/youtube`, {
      method: "POST",
      body: JSON.stringify({ channel, since_days: sinceDays, max_videos: maxVideos }),
    });
    revalidatePath("/kinerja");
    return { ok: true, result };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message };
    throw e;
  }
}
