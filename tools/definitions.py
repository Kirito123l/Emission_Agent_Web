"""
Tool Definitions for Tool Use Mode
Defines all tools in OpenAI function calling format
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_emission_factors",
            "description": """Query vehicle emission factor curves.

Use this when:
- User wants to know emission factors for a vehicle type
- User asks about emission characteristics at different speeds
- User wants to compare emissions at different speeds

Output: Speed-emission factor relationship chart + key data points table""",
            "parameters": {
                "type": "object",
                "properties": {
                    "vehicle_type": {
                        "type": "string",
                        "description": "Vehicle type. Pass user's original expression (e.g., '小汽车', '公交车', 'SUV'). System will automatically recognize it."
                    },
                    "pollutant": {
                        "type": "string",
                        "description": "Single pollutant name (e.g., 'CO2', 'NOx', 'PM2.5'). Use this for single pollutant query."
                    },
                    "pollutants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of pollutants for multi-pollutant query. Use this instead of 'pollutant' when querying multiple pollutants."
                    },
                    "model_year": {
                        "type": "integer",
                        "description": "Vehicle model year (e.g., 2020). Range: 1995-2025."
                    },
                    "season": {
                        "type": "string",
                        "description": "Season (春季/夏季/秋季/冬季). Optional, defaults to summer if not provided."
                    },
                    "road_type": {
                        "type": "string",
                        "description": "Road type (快速路/地面道路). Optional, defaults to expressway if not provided."
                    },
                    "return_curve": {
                        "type": "boolean",
                        "description": "Whether to return full curve data. Default false."
                    }
                },
                "required": ["vehicle_type", "model_year"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_micro_emission",
            "description": """Calculate detailed emissions for a single vehicle trajectory (microscopic emission).

Use this when:
- User has second-by-second trajectory data (speed over time)
- User uploaded a trajectory file
- User wants to calculate emissions for a specific trip

**IMPORTANT**: When user uploads a file, you will see the file path in the context. Use that file_path parameter to calculate emissions.

Input: Trajectory data (time + speed, acceleration and grade optional)
Output: Second-by-second emission details + total emission summary + downloadable Excel file""",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to trajectory data file. REQUIRED when user uploaded a file. You will see this path in the file context."
                    },
                    "trajectory_data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Trajectory data array. Each point should have 't' (time in seconds) and 'speed_kph' (speed in km/h). Use this if user provides data directly."
                    },
                    "vehicle_type": {
                        "type": "string",
                        "description": "Vehicle type. Pass user's original expression. REQUIRED."
                    },
                    "pollutants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of pollutants to calculate. Defaults to [CO2, NOx, PM2.5] if not provided."
                    },
                    "model_year": {
                        "type": "integer",
                        "description": "Vehicle model year. Defaults to 2020 if not provided."
                    },
                    "season": {
                        "type": "string",
                        "description": "Season. Optional."
                    }
                },
                "required": ["vehicle_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_macro_emission",
            "description": """Calculate road link emissions (macroscopic emission).

Use this when:
- User has road link data (length, traffic flow, speed)
- User uploaded a road network file
- User wants to calculate emissions for a road segment or network

Input: Link data (length + flow + speed, fleet composition optional)
Output: Per-link emission details + total emission summary + downloadable Excel file""",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to road link data file."
                    },
                    "links_data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Road link data array. Each link should have 'link_length_km', 'traffic_flow_vph', 'avg_speed_kph'. Use this if user provides data directly."
                    },
                    "pollutants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of pollutants to calculate."
                    },
                    "fleet_mix": {
                        "type": "object",
                        "description": "Fleet composition (vehicle type percentages). Optional, uses default if not provided."
                    },
                    "model_year": {
                        "type": "integer",
                        "description": "Vehicle model year."
                    },
                    "season": {
                        "type": "string",
                        "description": "Season. Optional."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_file",
            "description": """Analyze uploaded file to identify its type and structure.

Use this when:
- User uploaded a file but didn't specify what to do with it
- Need to understand file content before processing
- File has non-standard column names

Output: File type (trajectory/road link/other), column list, data preview, suggested processing method""",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to analyze"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge",
            "description": """Query emission-related knowledge, standards, and regulations from knowledge base.

Use this when:
- User asks about emission standards (e.g., "什么是国六排放标准")
- User wants to know regulations or policies
- User asks about technical concepts or definitions
- User asks about testing methods or procedures (e.g., "机动车尾气检测有哪些方法")
- User asks about measurement standards or protocols
- User needs reference information about emissions
- User asks "what is", "how to", "what are the methods" type questions

Output: Answer based on knowledge base with source references""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or topic to search for in the knowledge base"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of knowledge entries to retrieve. Optional, defaults to 5."
                    },
                    "expectation": {
                        "type": "string",
                        "description": "Expected type of information (e.g., 'standard definition', 'regulation details'). Optional."
                    }
                },
                "required": ["query"]
            }
        }
    }
]
