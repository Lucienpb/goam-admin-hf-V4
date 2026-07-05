def summarize_course(df, course: str):
    cdf = df[df["course"].str.lower() == course.lower()]

    if cdf.empty:
        return {"error": f"No rounds found at {course}"}

    return {
        "course": course,
        "rounds": len(cdf),
        "players": sorted(cdf["player"].unique().tolist()),
        "avg_ips": float(cdf["ips"].mean()),
        "best_ips": float(cdf["ips"].max()),
        "worst_ips": float(cdf["ips"].min()),
        "avg_strokes": float(cdf["strokes"].mean()),
    }

