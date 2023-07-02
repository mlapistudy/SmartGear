# README

This part is built upon several exisiting tools.

## How to run

Please specify CVC path before execution, e.g:
```bash
export PYTHONPATH=/usr/local/share/pyshared/
```

We provide an input example at `my_tool/example/`
```bash
cd my_tool
python3 get_control_flow.py --input_json=example/input.json --output_json=example/output.json --log_file=example/log.txt
```

`input_json` should be in format as:
```json
{
  "func_name": "find_dessert",
  "code_file": "example/dessert.py",
  "func_def_line": 10,
  "input_types": [
    "string"
  ],
  "API_param": [
    "image_path"
  ],
  "workspace": "example/"
}
```
- `func_name` is the name of the function to be tested. 
- `code_file` is the file that contains the definition of the tested function (do not need to contain its callees, but we suggest so to reduce potential failure ). Please make sure the program is executable, otherwise this tool would terminate,
- `func_def_line` is the line # of the head of function to be tested. It starts counting from 1.
- `input_types` is the type of input parameter, in the same order as function definition. It could be `"integer"`, `"float"` , `"boolean"`, or `"string"`.
- `API_param` is the input parameters that are ML API input. We currently only support a single API param.
- `workspace` is the working space of the tested function. 


## Result
Result looks like
```json
{
    "conditions": {
        "label_detection": [
            [
                ""
            ],
            [
                "dessert"
            ]
        ]
    },
    "exact_match": false,
    "exclusive": true,
    ...
}
```

1. In `whitelist`, `[""]` means otherwise case.
2. `exact_match` would be `true` if branch condition is equal instead of substring
3. `break` would be `true` if branches exclusive with each other
4. Others are logging infos.