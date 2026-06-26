CREATE POLICY "Public can read persons" ON localize.persons
    FOR SELECT
    USING (true);

CREATE POLICY "Public can read notes" ON localize.notes
    FOR SELECT
    USING (true);
