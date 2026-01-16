-- Fix duplicate UUIDs for all tables
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT id FROM core_categoria LOOP
        UPDATE core_categoria SET uuid = gen_random_uuid() WHERE id = r.id;
    END LOOP;
    FOR r IN SELECT id FROM core_formapagamento LOOP
        UPDATE core_formapagamento SET uuid = gen_random_uuid() WHERE id = r.id;
    END LOOP;
    FOR r IN SELECT id FROM core_conta LOOP
        UPDATE core_conta SET uuid = gen_random_uuid() WHERE id = r.id;
    END LOOP;
    FOR r IN SELECT id FROM core_configusuario LOOP
        UPDATE core_configusuario SET uuid = gen_random_uuid() WHERE id = r.id;
    END LOOP;
    FOR r IN SELECT id FROM core_logimportacao LOOP
        UPDATE core_logimportacao SET uuid = gen_random_uuid() WHERE id = r.id;
    END LOOP;
    FOR r IN SELECT id FROM investimento_ativo LOOP
        UPDATE investimento_ativo SET uuid = gen_random_uuid() WHERE id = r.id;
    END LOOP;
    FOR r IN SELECT id FROM investimento_classeativo LOOP
        UPDATE investimento_classeativo SET uuid = gen_random_uuid() WHERE id = r.id;
    END LOOP;
END $$;
