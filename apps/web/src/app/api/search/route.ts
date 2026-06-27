import { NextResponse } from "next/server";
import { createServiceClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("q") ?? "";

  try {
    const supabase = createServiceClient();
    const { data, error } = await supabase.rpc("search_persons", {
      search_query: query.trim(),
      result_limit: 50,
    });

    if (error) {
      console.error("search_persons error:", error);
      return NextResponse.json(
        { error: "No se pudo realizar la búsqueda. Intenta de nuevo." },
        { status: 500 }
      );
    }

    return NextResponse.json({ results: data ?? [] });
  } catch (err) {
    console.error("search route error:", err);
    return NextResponse.json(
      { error: "Error inesperado del servidor." },
      { status: 500 }
    );
  }
}
