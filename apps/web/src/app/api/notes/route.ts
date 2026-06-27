import { NextResponse } from "next/server";
import { createServiceClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const personRecordId = searchParams.get("person_record_id");

  if (!personRecordId) {
    return NextResponse.json(
      { error: "person_record_id is required" },
      { status: 400 }
    );
  }

  try {
    const supabase = createServiceClient();
    const { data, error } = await supabase
      .from("notes")
      .select("note_text, author_name, status, source_date, created_at")
      .eq("person_record_id", personRecordId)
      .order("created_at", { ascending: false });

    if (error) {
      console.error("notes fetch error:", error);
      return NextResponse.json(
        { error: "No se pudieron obtener las notas." },
        { status: 500 }
      );
    }

    return NextResponse.json({ notes: data ?? [] });
  } catch (err) {
    console.error("notes route error:", err);
    return NextResponse.json(
      { error: "Error inesperado del servidor." },
      { status: 500 }
    );
  }
}
