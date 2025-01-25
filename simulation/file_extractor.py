import zipfile
import os
import tempfile
import shutil
from io import BytesIO
import sys

class FileExtractor:
    def __init__(self):
        self.temp_files = {}

    def extract(self, zip_data, job_id, extensions=['.raw', '.log']):
        """ZIPデータを解凍して、指定された拡張子のファイルのパスを返す関数"""
        extraction_dir = None
        extracted_files = {}
        try:
            with zipfile.ZipFile(BytesIO(zip_data)) as zip_ref:
                extraction_dir = tempfile.mkdtemp()

                for file_name in zip_ref.namelist():
                    zip_ref.extract(file_name, extraction_dir)
                    for ext in extensions:
                        if file_name.endswith(ext):
                            extracted_files[ext] = os.path.join(extraction_dir, file_name)

                if not extracted_files:
                    print(f"Error: No files with specified extensions found in the ZIP file for job {job_id}.", file=sys.stderr)
                    return None

                self.temp_files[job_id] = {'files': extracted_files, 'dir': extraction_dir}
                # print(f"Job results extracted: {extracted_files}")
                return extracted_files

        except zipfile.BadZipFile:
            print(f"Error: The file for job {job_id} is not a valid ZIP file.", file=sys.stderr)
        except Exception as e:
            print(f"Error extracting files for job {job_id}: {str(e)}", file=sys.stderr)
        
        return None

    def list(self, job_id):
        """指定したジョブIDの抽出されたファイル一覧を表示"""
        if job_id in self.temp_files:
            files = self.temp_files[job_id].get('files', {})
            if files:
                print(f"Files extracted for job {job_id}:")
                for ext, file_path in files.items():
                    print(f"{ext}: {file_path}")
            else:
                print(f"No files extracted for job {job_id}.", file=sys.stderr)
        else:
            print(f"No files found for job {job_id}.", file=sys.stderr)

    def cleanup(self, job_id):
        """ジョブ結果に関連する一時ファイルを削除する関数"""
        if job_id in self.temp_files:
            temp_files = self.temp_files.pop(job_id)
            extraction_dir = temp_files.get('dir')

            if extraction_dir and os.path.exists(extraction_dir):
                # 解凍したディレクトリとファイルを再帰的に削除
                shutil.rmtree(extraction_dir)
                print(f"Temporary files for job ID {job_id} have been deleted.")
            else:
                print(f"Extraction directory for job ID {job_id} not found.", file=sys.stderr)
        else:
            print(f"No temporary files found for job ID {job_id}.", file=sys.stderr)
