import os
import re

def remove_i18n_fallbacks(directory):
    # Matches t('key', 'fallback text') or t("key", "fallback text") or t(`key`, `fallback text`)
    # and replaces with t('key')
    pattern = re.compile(r"(t\s*\(\s*(['\"`].*?['\"`]))\s*,\s*(['\"`].*?['\"`])\s*\)")
    
    count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tsx'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = pattern.sub(r"\1)", content)
                
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f'Updated: {path}')
                    count += 1
    print(f"Total files updated: {count}")

if __name__ == '__main__':
    target_dir = '/home/batnini/meeting-automation/frontend/src/components'
    remove_i18n_fallbacks(target_dir)
