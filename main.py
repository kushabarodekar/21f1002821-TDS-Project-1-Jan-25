# /// script
# requires-python = ">=3.13"
# dependencies = [
# "fastapi",
# "uvicorn",
# "requests",
# "numpy",
# "scikit-learn",
# "datetime",
# "python-dateutil"
# ]
# ///
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import numpy as np
from typing import List
import json 
import requests
import base64
from itertools import combinations
import os
import subprocess
import traceback
import dateutil.parser
from datetime import datetime
import glob
import base64
import sqlite3

API_KEY = os.getenv("AIPROXY_TOKEN")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"]   # Allow all headers
)

def generate_data(file_url:str,user_email:str):
    #runnning command
    try :
        command = ["uv" , "run" , file_url , user_email, "--root", "./data"]
        subprocess.run(command)
    except Exception as e:
        return {"status":"Data files generation un-successful"}
    return {"status":"Data files generated successfully"}


def format_file(file_path:str,formatter:str):
    try:
        #subprocess.run(["chmod" , "755" , "."+file_path])
        subprocess.run(["npm", "install", "--no-fund", "-g", formatter] , check=True)
        subprocess.run(["npx", formatter, "--write",  "."+file_path], shell=True, check=True)
        return {"status":"File Formatted successfully","file_path":file_path}
    except Exception as e:
        print(e)
    return {"status":"File Formatting un-successful"}

def parse_and_format_date(date_str):
    """
    Try to parse the date using dateutil and convert it to '%Y-%m-%d' format.
    """
    try:
        parsed_date = dateutil.parser.parse(date_str.strip())
        return parsed_date.strftime("%Y-%m-%d")  # Convert to standard format
    except (ValueError, TypeError):
        return None  # Return None if the date is invalid

def count_weekday(input_file_path:str,weekday:str,output_file_path:str):
    target_weekday = weekday.capitalize()  # Ensure proper capitalization
    valid_weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in valid_weekdays:
        if day in target_weekday or target_weekday in day:
            target_weekday = day

    count = 0

    with open("."+input_file_path, "r") as file:
        for line in file:
            formatted_date = parse_and_format_date(line)
            if formatted_date:
                parsed_date = datetime.strptime(formatted_date, "%Y-%m-%d")
                if parsed_date.strftime("%A") == target_weekday:
                    count += 1

    with open("."+output_file_path, "w") as file:
        file.write(str(count) + "\n")
    
    return {"status":"File Saved Sucessfully","output_file_path":output_file_path}


def sort_contacts(input_file_path:str,user_input_1:str,user_input_2:str,output_file_path:str):
    with open("."+input_file_path, "r") as file:
            contacts = json.load(file)

    # Sorting contacts by primary and secondary criteria
    sorted_contacts = sorted(contacts, key=lambda x: (x.get(user_input_1, ""), x.get(user_input_2, "")))

    # Write sorted contacts to the output JSON file
    with open("."+output_file_path, "w") as file:
        json.dump(sorted_contacts, file, indent=4)

    return {"status":"Contacts Sorted Sucessfully","output_file_path":output_file_path}

def write_most_recent_logs(input_location:str,output_file_path:str):
    # Get a list of .log files sorted by modification time (most recent first)
    log_files = sorted(glob.glob(os.path.join("."+input_location, "*.log")), key=os.path.getmtime, reverse=True)[:10]

    # Read the first line from each log file and store results
    log_lines = []
    for log_file in log_files:
        try:
            with open(log_file, "r") as file:
                first_line = file.readline().strip()
                if first_line:
                    log_lines.append(first_line)
        except Exception as e:
            print(f"❌ Error reading {log_file}: {e}")

    # Write collected lines to output file
    with open("."+output_file_path, "w") as file:
        file.write("\n".join(log_lines) + "\n")
    
    return {"status":"Recent Logs Saved Sucessfully","output_file_path":output_file_path}

def extract_title(file_path,heading):
    """Extract the first H1 title (# Title) from a Markdown file."""
    heading = heading.capitalize()
    headings = {"H1":"# ","H2":"## ","H3":"### ","H4":"#### ","H5":"##### ","H6":"###### ",}
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line.startswith(headings[heading]):  # H1 title found
                    return line[2:].strip()  # Remove "# " and return the title
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
    return None  # Return None if no H1 title is found

def extract_and_map_headings_to_filename(input_location:str,heading:str,output_file_path:str):
    index = {}

    # Find all Markdown files in /data/docs/ (including subdirectories)
    md_files = glob.glob(os.path.join("."+input_location, "**", "*.md"), recursive=True)

    for md_file in md_files:
        filename = os.path.relpath(md_file, "."+input_location)  # Get relative path
        title = extract_title(md_file,heading)

        if title:  # Only add if a title was found
            index[filename] = title

    # Write the index to JSON file
    with open("."+output_file_path, "w", encoding="utf-8") as file:
        json.dump(index, file, indent=4)

    return {"status":"Mapping File Saved Sucessfully","output_file_path":output_file_path}


def extract_sender_email(input_file_path:str,output_file_path:str):
    with open("."+input_file_path, "r", encoding="utf-8") as file:
        email_text = file.read()
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        }
        data = {
        "model": "gpt-4o-mini",
        "response_format": { "type": "text" },
        "messages": [
            {
                "role": "system",
                "content": """
                                Extract the sender's email address from the following email text:
                                The email is formatted as an email message with headers such as 'From:', 'To:', 'Subject:', etc.
                                If the 'From:' field contains a name and email (e.g., "John Doe <john@example.com>"), extract only the email inside the angle brackets.
                                If the 'From:' field contains only an email address, return it as is.
                                If the 'From:' field is missing, return 'No sender email found'.
                                Only return the email address as plain text. Do not include any extra words.
                            """
            },
            {
                "role": "user",
                "content": email_text
            }
            ]
        }
        response = requests.post("https://aiproxy.sanand.workers.dev/openai/v1/chat/completions", headers=headers, json=data)
        sender_email = response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        if 400 <= response.status_code < 500:
            raise HTTPException(status_code=400, detail="Bad Request : "+response.text)
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error ")
    with open("."+output_file_path, "w") as file:
        file.write(str(sender_email))
    return {"status":"Sender's Email Saved Sucessfully","output_file_path":output_file_path}

def extract_card_number_from_image(image_file_path:str,output_file_path:str):
    with open("."+image_file_path, 'rb') as f:
        binary_data = f.read()
        image_b64 = base64.b64encode(binary_data).decode()

    extension = image_file_path.split(".")[-1]

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        }
        data = {
        "model": "gpt-4o-mini",
        "response_format": { "type": "text" },
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                    "type": "text",
                    # We ask for a JSON response here (but don't enforce it via structured outputs)
                    "text": "Extract the largest number from the image and return only that number"
                    },
                    {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{extension};base64,{image_b64}"
                        }
                    }
                ]
            }
            ]
        }
        response = requests.post("https://aiproxy.sanand.workers.dev/openai/v1/chat/completions", headers=headers, json=data)
        card_number = response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        if 400 <= response.status_code < 500:
            raise HTTPException(status_code=400, detail="Bad Request : "+response.text)
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error ")
    
    with open("."+output_file_path, "w") as file:
        file.write(str(card_number))
    return {"status":"Card Number Saved Sucessfully","output_file_path":output_file_path}

def generate_embedding(commentList):
    try :
        # Placeholder for the "text-embedding-3-small" model
        #return np.random.rand(1, 128)  # 128-dimensional random embedding
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        }
        data = {}
        data["model"] = "text-embedding-3-small"
        data["input"] = commentList
        jsonInput = json.dumps(data)
        response = requests.post("https://aiproxy.sanand.workers.dev/openai/v1/embeddings", headers=headers, data=jsonInput)
        response.raise_for_status()  # Raise an exception for bad status codes
        embedding = response.json()["data"]
    except Exception as e:
        print(e)
        if 400 <= response.status_code < 500:
            raise HTTPException(status_code=400, detail="Bad Request : "+response.text)
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error ")
    return embedding

# Compute cosine similarity
def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def find_similar_comments(input_file_path:str,output_file_path:str):
    try:
        with open("."+input_file_path, "r", encoding="utf-8") as file:
            comments = [line.strip() for line in file if line.strip()]

        commentList = []
        for comment in comments:
            commentList.append(comment)

        embeddingList = generate_embedding(commentList)
        embeddings = {}
        for i in range(len(commentList)):
            comment = commentList[i]
            if i == 0:
                print(comment)
                print(embeddingList[i]["embedding"])
            embedding = embeddingList[i]["embedding"]
            embeddings[comment] = embedding

        # Find the most similar pair
        max_similarity = -1
        most_similar_pair = None



        for comment1, comment2 in combinations(comments, 2):
            similarity = cosine_similarity(embeddings[comment1], embeddings[comment2])
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_pair = (comment1, comment2)

        # Write the most similar comments to file
        if most_similar_pair:
            with open("."+output_file_path, "w", encoding="utf-8") as file:
                file.write("\n".join(most_similar_pair))
    except Exception as e:
           print(e)
           raise HTTPException(status_code=500, detail="Internal Server Error ")

    

def calculate_gold_ticket_sales(db_file_location:str,ticket_type:str,output_file_path:str):
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect("."+db_file_location)
        cursor = conn.cursor()

        # Use parameterized query to prevent SQL injection
        cursor.execute("SELECT SUM(units * price) FROM tickets WHERE type = ?", (ticket_type,))
        total_sales = cursor.fetchone()[0]  # Fetch result

        # Ensure None is handled (if no matching tickets exist)
        total_sales = total_sales if total_sales else 0

        # Write the result to the output file
        with open("."+output_file_path, "w", encoding="utf-8") as file:
            file.write(str(total_sales))
    except Exception as e:
        print(f"❌ Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error ")
    finally:
        if conn:
            conn.close()  # Close the database connection


GENERATE_DATA_TOOLS = {
      "type":"function",
      "function":{
         "name":"generate_data",
         "description":"Generate the uv script and generates data files to perform susequent operations",
         "parameters":{
            "type":"object",
            "properties":{
               "file_url":{
                  "type":"string",
                  "description":"URL location of the file"
               },
               "user_email":{
                  "type":"string",
                  "description":"Email Address of the user"
               }
            },
            "required":[
               "file_url",
               "user_email"
            ],
            "additionalProperties":False
         },
         "strict":True
      }
   }

FILE_FORMAT_TOOLS = {
      "type":"function",
      "function":{
         "name":"format_file",
         "description":"Format the contents of /data/format.md using formatter like prettier@3.4.2 in place",
         "parameters":{
            "type":"object",
            "properties":{
               "file_path":{
                  "type":"string",
                  "description":"Relative path of the .md file"
               },
               "formatter":{
                   "type":"string",
                   "description":"Fomatter to be used to format .md file"
               }
            },
            "required":[
               "file_path",
               "formatter"
            ],
            "additionalProperties":False
         },
         "strict":True
      }
   }

COUNT_WEEKDAY_TOOLS = {
      "type":"function",
      "function":{
         "name":"count_weekday",
         "description":"Count number of weekday(eg: Wednesday) from input date file and write it in output file ",
         "parameters":{
            "type":"object",
            "properties":{
               "input_file_path":{
                  "type":"string",
                  "description":"Relative path of the date file"
               },
               "weekday":{
                  "type":"string",
                  "description":"Exact day of the week that needs to be counted"
               },
               "output_file_path":{
                  "type":"string",
                  "description":"Relative path to save the output file"
               }
            },
            "required":[
               "input_file_path",
               "weekday",
               "output_file_path"
            ],
            "additionalProperties":False
         },
         "strict":True
      }
   }

SORT_CONTACT_TOOLS = {
   "type":"function",
   "function":{
      "name":"sort_contacts",
      "description":"Sort the array of contacts from input json by user input eg: by last_name, then first_name and then write it to output json",
      "parameters":{
         "type":"object",
         "properties":{
            "input_file_path":{
               "type":"string",
               "description":"Relative path of the contacts json file"
            },
            "user_input_1":{
               "type":"string",
               "description":"Primary field by which we want to sort"
            },
            "user_input_2":{
               "type":"string",
               "description":"Secondary field by which we want to sort"
            },
            "output_file_path":{
               "type":"string",
               "description":"Relative path to save sorted contacts json file"
            }
         },
         "required":[
            "input_file_path",
            "user_input_1",
            "user_input_2",
            "output_file_path"
         ],
         "additionalProperties":False
      },
      "strict":True
   }
}

WRITE_RECENT_LOGS_TOOLS = {
      "type":"function",
      "function":{
         "name":"write_most_recent_logs",
         "description":"Write the first line of the 10 most recent .log file present at input location and write it to output file",
         "parameters":{
            "type":"object",
            "properties":{
               "input_location":{
                  "type":"string",
                  "description":"Relative path of the .log file"
               },
               "output_file_path":{
                  "type":"string",
                  "description":"Relative path of output file to save the most recent logs"
               }
            },
            "required":[
               "input_location",
               "output_file_path"
            ],
            "additionalProperties":False
         },
         "strict":True
      }
   }

EXTRACT_MAP_TOOLS = {
   "type":"function",
   "function":{
      "name":"extract_and_map_headings_to_filename",
      "description":"Find all markdown files in input location, extract first H1 from file, create a new json file having map in format filename:heading",
      "parameters":{
         "type":"object",
         "properties":{
            "input_location":{
               "type":"string",
               "description":"Relative location of the folder where all .md files reside"
            },
            "heading":{
               "type":"string",
               "description":"HTML tag that needs to be extracted from .md file"
            },
            "output_file_path":{
               "type":"string",
               "description":"Relative path of the json file to save the final output "
            }
         },
         "required":[
            "input_location",
            "heading",
            "output_file_path"
         ],
         "additionalProperties":False
      },
      "strict":True
   }
}

EXTRACT_SENDER_EMAIL_TOOLS = {
   "type":"function",
   "function":{
      "name":"extract_sender_email",
      "description":"Extract only sender email from input email file and write it to output file ",
      "parameters":{
         "type":"object",
         "properties":{
            "input_file_path":{
               "type":"string",
               "description":"Relative path of the .txt file having email content"
            },
            "output_file_path":{
               "type":"string",
               "description":"Relative path of the file where we need to save the sender's email address"
            }
         },
         "required":[
            "input_file_path",
            "output_file_path"
         ],
         "additionalProperties":False
      },
      "strict":True
   }
}

EXTRACT_CARD_NUMBER_TOOLS = {
      "type":"function",
      "function":{
         "name":"extract_card_number_from_image",
         "description":"Extract card number from image file and write it to output file",
         "parameters":{
            "type":"object",
            "properties":{
               "image_file_path":{
                  "type":"string",
                  "description":"Relative path of the image(.png/.jpg/.jpeg/.svg) file "
               },
               "output_file_path":{
                  "type":"string",
                  "description":"Relative path of the .txt file to save the card number from the image"
               }
            },
            "required":[
               "image_file_path",
               "output_file_path"
            ],
            "additionalProperties":False
         },
         "strict":True
      }
   }

FIND_SIMILAR_COMMENT_TOOLS = {
      "type":"function",
      "function":{
         "name":"find_similar_comments",
         "description":"Find similar comments from input comments file and write similar pairs of comments in output file",
         "parameters":{
            "type":"object",
            "properties":{
               "input_file_path":{
                  "type":"string",
                  "description":"Relative path of the input comments file(.txt)"
               },
               "output_file_path":{
                  "type":"string",
                  "description":"Relative path of the output file(.txt) where we want to save the similar pair of comments"
               }
            },
            "required":[
               "input_file_path",
               "output_file_path"
            ],
            "additionalProperties":False
         },
         "strict":True
      }
   }

CALCULATE_SALES_TOOLS = {
      "type":"function",
      "function":{
         "name":"calculate_gold_ticket_sales",
         "description":"Extract entries from database file, filter it for gold type tickets, calculate its total sales and write it into output file ",
         "parameters":{
            "type":"object",
            "properties":{
               "db_file_location":{
                  "type":"string",
                  "description":"Relative path of the .db file"
               },
               "ticket_type":{
                  "type":"string",
                  "description":"ticket type for which the total sales needs to be calculated"
               },
               "output_file_path":{
                  "type":"string",
                  "description":"Relative path of the file(.txt) where we want to save the total sales of the ticket type"
               }
            },
            "required":[
               "db_file_location",
               "ticket_type",
               "output_file_path"
            ],
            "additionalProperties":False
         },
         "strict":True
      }
   }

tools = [GENERATE_DATA_TOOLS, FILE_FORMAT_TOOLS, COUNT_WEEKDAY_TOOLS, SORT_CONTACT_TOOLS, 
         WRITE_RECENT_LOGS_TOOLS,EXTRACT_MAP_TOOLS, EXTRACT_MAP_TOOLS, EXTRACT_SENDER_EMAIL_TOOLS, 
         EXTRACT_CARD_NUMBER_TOOLS, FIND_SIMILAR_COMMENT_TOOLS, CALCULATE_SALES_TOOLS]

class RequestBody(BaseModel):
    docs: List[str]
    query: str

def queryLLM(query):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        }
        data = {"model": "gpt-4o-mini", 
                "messages": [{"role": "user", "content": query}],
                "tools": tools,
                "tool_choice": "auto",
                }
        response = requests.post("https://aiproxy.sanand.workers.dev/openai/v1/chat/completions", headers=headers, json=data)
    except Exception as e:
        if 400 <= response.status_code < 500:
            raise HTTPException(status_code=400, detail="Bad Request : "+response.text)
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error ")
    response.raise_for_status() 
    return response

def getToolJson():
    # Read JSON file
    with open("tool.json", "r") as file:
        tools = json.load(file)
    return tools


@app.get("/")
def home():
    return ("First API Done")

@app.get("/read")
def read_file(path:str):
    try:
        with open("."+path,"r") as f:
            return PlainTextResponse(f.read())
    except Exception as e:
        raise HTTPException(status_code=404, details="Item Not Found")
    
@app.post("/run")
def task_runner(task : str):
    try :
        response = queryLLM(task)
        jsonOutput = response.json()["choices"][0]["message"]["tool_calls"][0]["function"]
        functionName = eval(jsonOutput["name"])
        functionArguements = json.loads(jsonOutput["arguments"])

        output = functionName(**functionArguements)
        return output
    except Exception as e:
        if 400 <= response.status_code < 500:
            raise HTTPException(status_code=400, detail="Bad Request : "+response.text)
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error ")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run (app, host="0.0.0.0", port=8000)
