import os
import json

def fix_rsi_meta(root_folder):
    print(f"Scanning: {root_folder}\n")

    for dirpath, dirnames, filenames in os.walk(root_folder):
        if dirpath.endswith('.rsi'):
            if 'meta.json' not in filenames:
                continue

            meta_path = os.path.join(dirpath, 'meta.json')

            try:
                with open(meta_path, 'r', encoding='utf-8-sig') as f:
                    meta_data = json.load(f)
            except Exception as e:
                print(f"[ERR] failed to read {meta_path}: {e}")
                continue

            existing_states = {state['name'] for state in meta_data.get('states', []) if 'name' in state}

            png_states = []
            for file in filenames:
                if file.lower().endswith('.png'):
                    state_name = os.path.splitext(file)[0]
                    png_states.append(state_name)

            missing_states = [state for state in png_states if state not in existing_states]

            if missing_states:
                print(f"RSI folder found: {os.path.basename(dirpath)}")

                if 'states' not in meta_data:
                    meta_data['states'] = []

                for missing in missing_states:
                    new_state = {"name": missing}
                    meta_data['states'].append(new_state)
                    print(f"  + State added: '{missing}'")

                try:
                    with open(meta_path, 'w', encoding='utf-8') as f:
                        json.dump(meta_data, f, indent=4, ensure_ascii=False)
                    print(f"  [DONE] File {os.path.basename(meta_path)} updated.\n")
                except Exception as e:
                    print(f"  [ERR] Failed to write changes to {meta_path}: {e}\n")

if __name__ == "__main__":
    PATH_TO_MOD = "./.."

    fix_rsi_meta(PATH_TO_MOD)
    print("Scanning and fixing completed.")
