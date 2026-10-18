from pathlib import Path
import re
import shutil
import subprocess
import sys
import os
import time
import yaml
import streamlit as st

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / 'profile.yaml'
CONFIG = ROOT / 'config.yaml'
CV_DIR = ROOT / 'cv'

st.set_page_config(page_title='JobApply Agent', page_icon='💼', layout='wide')
st.title('💼 JobApply Agent')
st.caption('Configuración local de tu perfil y búsqueda laboral')
def candidate_location(profile):
    country = str(profile.get("country", "")).strip()
    city = str(profile.get("city", "")).strip()

    if not country:
        raise ValueError(
            "El perfil debe indicar un país de residencia."
        )

    return {
        "country": country,
        "city": city,
        "work_mode": profile.get("work_mode", ""),
        "preferences": profile.get("job_preferences", {}),
    }
def read_yaml(path):
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def save_yaml(path, data):
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + '.bak'))
    with path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

profile = read_yaml(PROFILE)
config = read_yaml(CONFIG)
tab_profile, tab_search, tab_status = st.tabs(['👤 Mi perfil', '🔎 Búsqueda', '📊 Estado'])

with tab_profile:
    st.subheader('Datos del candidato')
    with st.form('profile_form'):
        a, b = st.columns(2)
        with a:
            first = st.text_input('Nombre', value=str(profile.get('first_name') or ''))
            email = st.text_input('Correo', value=str(profile.get('email') or ''))
            city = st.text_input('Ciudad', value=str(profile.get('city') or ''))
            github = st.text_input('GitHub', value=str(profile.get('github') or ''))
        with b:
            last = st.text_input('Apellido', value=str(profile.get('last_name') or ''))
            phone = st.text_input('Teléfono', value=str(profile.get('phone') or ''))
            country = st.text_input('País', value=str(profile.get('country') or ''))
            linkedin = st.text_input('LinkedIn', value=str(profile.get('linkedin') or ''))
        summary = st.text_area('Resumen profesional', value=str(profile.get('summary') or ''), height=180)
        submitted = st.form_submit_button('Guardar perfil', type='primary')
        if submitted:
            profile.update(first_name=first.strip(), last_name=last.strip(), email=email.strip(), phone=phone.strip(), city=city.strip(), country=country.strip(), github=github.strip(), linkedin=linkedin.strip(), summary=summary.strip())
            save_yaml(PROFILE, profile)
            st.success('Perfil guardado en profile.yaml (copia de seguridad .bak).')
    st.divider()
    st.subheader('Adjuntar CV')
    cv = st.file_uploader('Selecciona un PDF o DOCX', type=['pdf', 'docx'])
    if cv is not None:
        if st.button('Guardar CV en carpeta cv'):
            CV_DIR.mkdir(parents=True, exist_ok=True)
            filename = Path(cv.name).name
            filename = re.sub(r'[^\w.\-]', '_', filename)
            if not filename.lower().endswith(('.pdf', '.docx')):
                st.error('Formato no permitido.')
            else:
                destination = CV_DIR / filename
                if destination.exists():
                    st.error('Ya existe un archivo con ese nombre. Renómbralo antes de subirlo.')
                else:
                    destination.write_bytes(cv.getvalue())
                    st.success(f'Guardado: cv/{filename}. Revisa config.yaml para asignarlo a las postulaciones.')
    st.info('Esta primera versión adjunta el CV, pero no extrae automáticamente su contenido ni modifica los años de experiencia.')

with tab_search:
    st.subheader('Configuración de búsqueda')
    st.write('Puedes ajustar los parámetros sin editar YAML a mano.')
    with st.form('search_form'):
        min_fit = st.slider('Compatibilidad mínima', 1, 10, int(config.get('min_fit', 5)))
        max_age = st.number_input('Antigüedad máxima de ofertas (días)', min_value=1, max_value=90, value=int(config.get('max_age_days', 7)))
        keywords = st.text_area('Palabras clave en títulos (una por línea)', value='\n'.join(config.get('title_keywords') or []), height=140)
        save_search = st.form_submit_button('Guardar configuración', type='primary')
        if save_search:
            config['min_fit'] = min_fit
            config['max_age_days'] = int(max_age)
            config['title_keywords'] = [x.strip() for x in keywords.splitlines() if x.strip()]
            save_yaml(CONFIG, config)
            st.success('Configuración guardada en config.yaml (copia de seguridad .bak).')
    st.divider()
    st.subheader('Ejecutar búsqueda con IA')
    st.caption('Se ejecuta el agente real con --dry-run: analiza ofertas, pero no envía postulaciones.')
    if st.button('▶ Ejecutar búsqueda (Dry Run)', type='primary', key='start_dry_run'):
        if not PROFILE.exists() or not CONFIG.exists():
            st.error('Falta profile.yaml o config.yaml.')
        elif not (os.environ.get('GEMINI_API_KEY') or '').strip():
            st.error('Falta GEMINI_API_KEY en el entorno desde el que iniciaste Streamlit.')
        else:
            env = os.environ.copy()
            env['JOBAGENT_LLM'] = 'gemini'
            env.setdefault('GEMINI_MODEL', 'gemini-3.5-flash-lite')
            command = [sys.executable, '-m', 'jobagent', '--dry-run']
            st.info('Ejecutando búsqueda. No cierres Streamlit. Puede abrirse Chrome para iniciar sesión o resolver verificaciones manualmente.')
            output = st.empty()
            lines = []
            try:
                process = subprocess.Popen(
                    command, cwd=str(ROOT), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace', bufsize=1,
                )
                for line in process.stdout:
                    lines.append(line.rstrip('\n'))
                    output.code('\n'.join(lines[-120:]) or 'Iniciando...', language='text')
                code = process.wait()
                st.session_state['last_run_output'] = '\n'.join(lines)
                st.session_state['last_run_code'] = code
                if code == 0:
                    st.success('Búsqueda finalizada. No se enviaron postulaciones (Dry Run).')
                else:
                    st.error(f'El agente terminó con código {code}. Revisa el registro mostrado.')
            except Exception as exc:
                st.error(f'No se pudo iniciar el agente: {type(exc).__name__}: {exc}')
    if st.session_state.get('last_run_output'):
        with st.expander('Ver registro de la última ejecución'):
            st.code(st.session_state['last_run_output'][-30000:], language='text')

with tab_status:
    st.subheader('Estado de archivos')
    st.write(f'Perfil: {"Disponible" if PROFILE.exists() else "No encontrado"}')
    st.write(f'Configuración: {"Disponible" if CONFIG.exists() else "No encontrada"}')
    st.write(f'CV disponibles: {len(list(CV_DIR.glob("*"))) if CV_DIR.exists() else 0}')
    st.code(
    'set "JOBAGENT_LLM=gemini"\n'
    'set "GEMINI_MODEL=gemini-2.5-flash-lite"\n'
    'python -m jobagent --dry-run',
    language="bat"
)
