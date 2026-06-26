CREATE POLICY "Public can read source_records" ON localize.source_records
    FOR SELECT
    USING (true);
