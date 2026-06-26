INSERT INTO localize.sources (id, name, namespace)
VALUES ('desaparecidos-terremoto-api', 'Desaparecidos Terremoto API', 'desaparecidosterremotovenezuela.com')
ON CONFLICT (id) DO NOTHING;
